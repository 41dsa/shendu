"""根据批改建议生成改写范例，并标注原文中值得保留的片段。"""

from __future__ import annotations

import difflib
import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import CredentialRole, Question, Report, Submission
from app.services.ai_client import AiCallError, chat_completion_json, get_credential
from app.services.essay_context import resolve_essay_context
from app.services.grading_service import log_usage
REWRITE_DEMO_SCHEMA_VERSION = 13

KEEP_SOLUTION_EXAMPLE_PREFIX = "续写示例，非对准问题，仅供参考："

MARKDOWN_BODY_INDENT = "\u3000\u3000"

# 单条 edit 与全文高亮占比上限，避免「全文标红」
_MAX_EDIT_SEGMENT_FRAC = 0.12
_MAX_HIGHLIGHT_COVERAGE = 0.28

REWRITE_DEMO_SYSTEM = """你是申论大作文写作教练。任务是在用户原文基础上做「局部润色与补改」，不是重写一篇新作文。
硬性要求：
1. rewrite_text 必须以 student_essay 为底稿：保留原文结构、标题（若有）、段落顺序与核心立意；仅针对 issues/suggestions 指出的短板做必要修改。
2. 全文被改写的字符量（相对原文的新增、替换、删除合计）不得超过约 30%；禁止整段另写、换题、换论证主线。
3. keep_segments（标准亮点句）：从 student_essay 中挑出 3～8 句「符合 scoring_rubric、写得特别好」的原文（quote 为连续子串，且须原封不动出现在 rewrite_text）；每条绑定一个 rubric 维度。须同时给出 keep_problem（该句仍存在的不足/风险，15～55 字，写入展示括号内）与 keep_solution（针对 keep_problem 的示范写法：1～2 句可直接借鉴的示例文字，可紧接原句续写或略作改写，25～100 字；必须是「怎么写」的例句，禁止「补写分析」「强化论证」等空泛指导）。reason 可省略（由系统合成）。
4. edit_segments：2～8 条，quote 必须是 rewrite_text 的连续子串，且只能是「改过的一小句/短语」（8～80 字）；禁止把整段、整节或全文作为一条 quote；与原文完全相同的句子不得列入。
5. change_summary：2～4 条，只描述局部改了什么，勿写「全文重写」类表述。
6. 排版（Markdown 范文）：与 student_essay 换行、空行一致；除标题行外，每个段落首行必须以两个全角空格「　　」开头；标题行不缩进、不居中。
仅输出 JSON：
{
  "rewrite_text": string,
  "keep_segments": [{"quote": string, "keep_problem": string, "keep_solution": string, "reason": string, "rubric_dimension_id": string, "rubric_dimension_label": string}],
  "edit_segments": [{"quote": string, "reason": string}],
  "change_summary": [string]
}
keep_segments 每条 quote 12～120 字；edit_segments 每条 quote 8～80 字。"""


def _max_edit_quote_len(rewrite_len: int) -> int:
    return min(72, max(14, int(rewrite_len * _MAX_EDIT_SEGMENT_FRAC)))


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_paragraphs(text: str) -> list[str]:
    """非空行块（仅用于统计），不改变原文行结构。"""
    lines = _normalize_newlines(text).split("\n")
    blocks: list[str] = []
    buf: list[str] = []
    for line in lines:
        if line.strip():
            buf.append(line)
        elif buf:
            blocks.append("\n".join(buf))
            buf = []
    if buf:
        blocks.append("\n".join(buf))
    return blocks


def _snap_to_sentence_end(text: str, pos: int) -> int:
    pos = max(0, min(len(text), pos))
    for i in range(pos, min(len(text), pos + 120)):
        if text[i] in "。！？；":
            return i + 1
    return pos


def _blank_pattern(lines: list[str]) -> list[bool]:
    return [not ln.strip() for ln in lines]


def _split_chunk_to_lines(chunk: str, line_count: int) -> list[str]:
    if line_count <= 1:
        return [chunk.strip()]
    sents = [s for s in re.split(r"(?<=[。！？；])", chunk) if s.strip()]
    if not sents:
        return [chunk.strip()] + [""] * (line_count - 1)
    if len(sents) >= line_count:
        per = max(1, len(sents) // line_count)
        lines: list[str] = []
        idx = 0
        for i in range(line_count):
            if i == line_count - 1:
                lines.append("".join(sents[idx:]).strip())
            else:
                lines.append("".join(sents[idx : idx + per]).strip())
                idx += per
        return lines
    lines = [s.strip() for s in sents]
    while len(lines) < line_count:
        lines.append("")
    return lines[:line_count]


def mirror_original_line_layout(original: str, rewrite: str) -> str:
    """改写范文行结构镜像用户原文：空行位置、行数与原文一致。"""
    orig_lines = _normalize_newlines(original).split("\n")
    rw_norm = _normalize_newlines(rewrite)
    rw_lines = rw_norm.split("\n")

    if not any(ln.strip() for ln in orig_lines):
        return rw_norm.strip()

    if len(rw_lines) == len(orig_lines) and _blank_pattern(orig_lines) == _blank_pattern(rw_lines):
        merged: list[str] = []
        for o, r in zip(orig_lines, rw_lines):
            merged.append(r if o.strip() else o)
        return "\n".join(merged)

    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(orig_lines):
        if not orig_lines[i].strip():
            i += 1
            continue
        start = i
        while i < len(orig_lines) and orig_lines[i].strip():
            i += 1
        blocks.append((start, i - 1))

    flat = re.sub(r"\s+", " ", rw_norm.replace("\n", " ")).strip()
    weights = [sum(len(orig_lines[j]) for j in range(s, e + 1)) or 1 for s, e in blocks]
    total = max(sum(weights), 1)

    filled: dict[int, str] = {}
    pos = 0
    for bi, (start, end) in enumerate(blocks):
        line_count = end - start + 1
        if bi == len(blocks) - 1:
            chunk = flat[pos:].strip()
        else:
            target = int(len(flat) * weights[bi] / total)
            endpos = _snap_to_sentence_end(flat, pos + max(16, target))
            if endpos <= pos:
                endpos = min(len(flat), pos + max(16, target))
            chunk = flat[pos:endpos].strip()
            pos = endpos
        sub_lines = _split_chunk_to_lines(chunk, line_count)
        for offset, line_idx in enumerate(range(start, end + 1)):
            filled[line_idx] = sub_lines[offset] if offset < len(sub_lines) else ""

    out: list[str] = []
    for idx, line in enumerate(orig_lines):
        if idx in filled:
            out.append(filled[idx])
        else:
            out.append(line)
    return "\n".join(out)


def _line_leading_indent(line: str) -> str:
    m = re.match(r"^([\u3000]{1,2}| {2,})", line)
    return m.group(1) if m else ""


def _strip_leading_indent(line: str) -> str:
    return re.sub(r"^[\u3000 ]+", "", line)


def _is_title_line(line: str) -> bool:
    t = line.strip()
    return bool(t) and len(t) <= 48 and not re.search(r"[。！？；]", t)


def detect_body_indent(original: str) -> str:
    for line in _normalize_newlines(original).split("\n"):
        if line.strip():
            ind = _line_leading_indent(line)
            if ind:
                return ind if "\u3000" in ind else MARKDOWN_BODY_INDENT
    return MARKDOWN_BODY_INDENT


def apply_markdown_paragraph_indent(original: str, text: str) -> str:
    """段首缩进与 Markdown 范文一致：正文「　　」，标题行不缩进。"""
    lines = _normalize_newlines(text).split("\n")
    orig_lines = _normalize_newlines(original).split("\n")
    indent = detect_body_indent(original)
    first_nonempty = next((i for i, ln in enumerate(orig_lines) if ln.strip()), 0)
    title_at = (
        first_nonempty
        if _is_title_line(orig_lines[first_nonempty]) and not _line_leading_indent(orig_lines[first_nonempty])
        else -1
    )

    out: list[str] = []
    for idx, line in enumerate(lines):
        if not line.strip():
            out.append(line)
            continue
        stripped = _strip_leading_indent(line)
        orig = orig_lines[idx] if idx < len(orig_lines) else ""
        if idx == title_at:
            out.append(stripped)
            continue
        block_start = idx == 0 or not lines[idx - 1].strip()
        if block_start:
            orig_ind = _line_leading_indent(orig) if orig.strip() else indent
            use = orig_ind or indent
            out.append(use + stripped if not line.startswith(use) else line)
        else:
            out.append(line)
    return "\n".join(out)


def format_rewrite_layout(original: str, rewrite: str) -> str:
    """行结构镜像原文 + Markdown 段首缩进。"""
    mirrored = mirror_original_line_layout(original, rewrite)
    return apply_markdown_paragraph_indent(original, mirrored)


def _filter_edits_against_keep(edit: list[dict[str, str]], keep: list[dict[str, str]]) -> list[dict[str, str]]:
    if not keep:
        return edit
    keep_quotes = [k.get("quote") or "" for k in keep if k.get("quote")]
    filtered: list[dict[str, str]] = []
    for row in edit:
        q = row.get("quote") or ""
        if not q:
            continue
        dominated = False
        for kq in keep_quotes:
            if q in kq or (kq in q and len(kq) / max(len(q), 1) >= 0.55):
                dominated = True
                break
        if not dominated:
            filtered.append(row)
    return filtered


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans)
    merged: list[tuple[int, int]] = [ordered[0]]
    for start, end in ordered[1:]:
        last = merged[-1]
        if start <= last[1]:
            merged[-1] = (last[0], max(last[1], end))
        else:
            merged.append((start, end))
    return merged


def _highlight_coverage(rewrite: str, segments: list[dict[str, str]]) -> float:
    if not rewrite or not segments:
        return 0.0
    spans: list[tuple[int, int]] = []
    for row in segments:
        quote = row.get("quote") or ""
        pos = rewrite.find(quote)
        if pos >= 0:
            spans.append((pos, pos + len(quote)))
    merged = _merge_spans(spans)
    covered = sum(end - start for start, end in merged)
    return covered / max(len(rewrite), 1)


def _best_similarity_in_haystack(needle: str, haystack: str) -> float:
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    n = len(needle)
    if n > len(haystack):
        return difflib.SequenceMatcher(None, needle, haystack).ratio()
    best = 0.0
    step = max(1, n // 4)
    for i in range(0, len(haystack) - n + 1, step):
        window = haystack[i : i + n]
        best = max(best, difflib.SequenceMatcher(None, needle, window).ratio())
        if best >= 0.96:
            break
    return best


def _iter_sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"[^\n。！？；]+[。！？；]?", text):
        chunk = match.group(0)
        if not chunk.strip():
            continue
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        start = match.start() + lead
        end = match.end() - trail
        if end > start:
            spans.append((start, end))
    if not spans and text.strip():
        spans.append((0, len(text)))
    return spans


def _iter_clause_spans(text: str, base: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"[^，、]+[，、]?", text):
        chunk = match.group(0)
        if not chunk.strip():
            continue
        lead = len(chunk) - len(chunk.lstrip())
        trail = len(chunk) - len(chunk.rstrip())
        start = base + match.start() + lead
        end = base + match.end() - trail
        if end > start and end - start >= 8:
            spans.append((start, end))
    return spans


def _validate_quote_segments(
    text: str,
    segments: Any,
    *,
    min_len: int = 8,
    max_items: int = 8,
    max_quote_len: int | None = None,
) -> list[dict[str, str]]:
    if not isinstance(segments, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[int, int]] = set()
    for row in segments:
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote") or "").strip()
        if len(quote) < min_len:
            continue
        if max_quote_len is not None and len(quote) > max_quote_len:
            continue
        pos = text.find(quote)
        if pos < 0:
            continue
        span = (pos, pos + len(quote))
        if span in seen:
            continue
        seen.add(span)
        reason = str(row.get("reason") or "").strip()[:240]
        out.append({"quote": quote, "reason": reason})
        if len(out) >= max_items:
            break
    return out


_RUBRIC_LABEL_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("立意", ("立意", "观点", "题意", "价值", "主旨", "标题")),
    ("结构", ("结构", "层次", "段落", "布局", "递进")),
    ("论证", ("论证", "论据", "案例", "分析", "因果", "素材", "材料")),
    ("语言", ("语言", "表达", "文字", "措辞", "修辞")),
)


def collect_rubric_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """本次报告采用的评分维度（标准 + 得分说明）。"""
    basis = payload.get("scoring_basis") if isinstance(payload.get("scoring_basis"), dict) else {}
    rubric = basis.get("scoring_points_rubric") or []
    scored = payload.get("scoring_points") or []
    ref_by_id = {
        str(r.get("id")): r for r in rubric if isinstance(r, dict) and r.get("id")
    }
    rows: list[dict[str, Any]] = []
    for sp in scored:
        if not isinstance(sp, dict):
            continue
        rid = str(sp.get("id") or "")
        ref = ref_by_id.get(rid) or {}
        rows.append(
            {
                "id": rid or str(ref.get("id") or ""),
                "label": str(sp.get("label") or ref.get("label") or "评分维度"),
                "max_score": sp.get("max") if sp.get("max") is not None else ref.get("max_score"),
                "earned": sp.get("earned"),
                "dimension_reason": str(sp.get("reason") or "").strip(),
            }
        )
    if not rows:
        for ref in rubric:
            if not isinstance(ref, dict):
                continue
            rows.append(
                {
                    "id": str(ref.get("id") or ""),
                    "label": str(ref.get("label") or "评分维度"),
                    "max_score": ref.get("max_score"),
                    "earned": None,
                    "dimension_reason": "",
                }
            )
    return rows


def _score_keep_for_rubric(blob: str, rubric_row: dict[str, Any]) -> int:
    score = 0
    label = str(rubric_row.get("label") or "")
    for _key, kws in _RUBRIC_LABEL_KEYWORDS:
        if any(k in label for k in (_key,)):
            for kw in kws:
                if kw in blob:
                    score += 2
    dim_note = str(rubric_row.get("dimension_reason") or "")
    for token in re.split(r"[，,。；;]\s*", dim_note):
        t = token.strip()
        if len(t) >= 4 and t in blob:
            score += 4
    if dim_note and len(set(dim_note) & set(blob)) >= 6:
        score += 2
    return score


def _plain_strength_hint(label: str, dim_note: str) -> str:
    if dim_note:
        short = re.sub(r"\s+", "", dim_note)
        return (short[:36] + "…") if len(short) > 36 else short
    for key, hint in (
        ("立意", "扣题清楚、观点稳"),
        ("观点", "扣题清楚、观点稳"),
        ("结构", "层次清楚、衔接自然"),
        ("论证", "分析到位、有说服力"),
        ("素材", "材料运用得当"),
        ("语言", "表达规范、有文采"),
    ):
        if key in label:
            return hint
    return "达到这一项的要求"


def _normalize_encourage_tail(text: str) -> str:
    t = text.replace("下次继续这么写", "继续保持").replace("下次继续这样写", "继续保持")
    t = re.sub(r"下次继续[^。；]*写", "继续保持", t)
    if t and not t.rstrip().endswith(("。", "！", "继续保持", "…")):
        if "继续保持" not in t[-12:]:
            t = f"{t.rstrip()}。继续保持"
    return t[:220]


def _extract_paren_problem(text: str) -> tuple[str, str, str]:
    """返回 (括号前, 括号内问题, 括号后剩余)。"""
    t = (text or "").strip()
    start = t.find("（")
    end = t.find("）", start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        return t, "", ""
    prefix = t[:start].strip()
    problem = t[start + 1 : end].strip()
    remainder = t[end + 1 :].strip()
    return prefix, problem, remainder


def _strip_encourage_from_tail(tail: str) -> tuple[str, str]:
    tail = (tail or "").strip()
    m = re.match(r"^(.*?)(继续保持[。．]*)$", tail)
    if not m:
        return tail.strip("。．、；; "), ""
    solution = m.group(1).strip().strip("。．、；; ")
    return solution, m.group(2).strip()


def _looks_like_generic_advice(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if t.startswith(KEEP_SOLUTION_EXAMPLE_PREFIX) or t.startswith("示例") or t.startswith("「") or t.startswith('"'):
        return False
    markers = (
        "补写",
        "强化",
        "保留原句",
        "保留该句",
        "针对括号",
        "针对上述",
        "在不删改",
        "使论证更饱满",
        "具体化分析",
        "可感知",
        "闭环。",
        "避免只引不析",
    )
    return any(m in t for m in markers)


def _format_solution_example(body: str) -> str:
    raw = (body or "").strip()
    if not raw:
        return ""
    if raw.startswith(KEEP_SOLUTION_EXAMPLE_PREFIX):
        return raw[:260]
    for old_prefix in ("示例：", "示例:"):
        if raw.startswith(old_prefix):
            raw = raw[len(old_prefix) :].strip()
            break
    inner = raw.strip("「」")
    return f"{KEEP_SOLUTION_EXAMPLE_PREFIX}「{inner}」"[:260]


def _infer_keep_solution_example(problem: str, quote: str, label: str) -> str:
    prob = (problem or "").strip()
    q = (quote or "").strip()

    if "观点+案例+分析" in prob or ("案例" in prob and "分析" in prob):
        return _format_solution_example(
            "这一认识在基层尤为真切：某社区以网格议事汇集民意、办结身边事，"
            "群众从旁观者变为参与者，观点、事例与分析由此贯通。"
        )
    if re.search(r"引.+后未", prob) or "未展开" in prob or "未衔接" in prob or "未分析" in prob or "王弼" in q:
        return _format_solution_example(
            "王弼所谓『物无妄然，必由其理』，推之于社会治理，就是要顺着群众诉求与运行机理施政，"
            "在尊重规律中提升精细化治理效能，而非主观蛮干。"
        )
    if "口号" in prob or "陈述" in prob:
        return _format_solution_example(
            "这一判断要落到具体场景——如少跑腿办成一件事、纠纷调解在一线化解，"
            "用可见成效证明观点，而不是停留在原则重复。"
        )
    if "结构" in label or "逻辑" in label:
        if "群众" in q or "人民" in q:
            return _format_solution_example(
                "在此可顺势点明分论点：依靠群众，关键在把议事协商、公开反馈、激励约束写进制度，"
                "让无源之水变为源头活水来。"
            )
        return _format_solution_example(
            "在此句后宜加衔接：上述认识为后文分论点奠基，下文可依次展开依靠谁、为了谁、如何干，"
            "避免并列堆砌。"
        )
    if "论证" in label or "论据" in label:
        return _format_solution_example(
            "例如可续写：以某县村寨银行与村规民约为例，群众自定规则、共管资源，"
            "说明观点并非空话，而是可复制的治理实践。"
        )
    if "语言" in label or "表达" in label:
        return _format_solution_example(
            "可将概括句稍具体化：把精细治理写成听得到诉求、看得见变化、管得住风险三件事，"
            "语言既规范又贴题。"
        )
    if prob:
        return _format_solution_example(
            "例如可续写：以一项基层可见做法（谁、怎么做、成效如何）回扣观点，"
            "再点明与分论点的因果关系，使保留句与后文连成一体。"
        )
    return _format_solution_example(
        "例如可续写：以一件与分论点相关的具体治理实践作例证，"
        "用做法和成效把观点写具体。"
    )


def _compose_keep_display_reason(label: str, problem: str) -> str:
    p = (problem or "").strip().rstrip("。")
    if not p:
        p = "整体表现不错，仍可再具体化"
    return _normalize_encourage_tail(f"这句话写得非常不错，符合「{label}」的要求（{p}）。继续保持。")


def _finalize_keep_segment_row(row: dict[str, Any], rubric_row: dict[str, Any]) -> dict[str, Any]:
    """合成 keep_problem / keep_solution 与展示用 reason。"""
    r = dict(row)
    label = str(rubric_row.get("label") or r.get("rubric_dimension_label") or "这一项")
    quote = str(r.get("quote") or "")

    problem = str(r.get("keep_problem") or "").strip()
    solution = str(r.get("keep_solution") or "").strip()
    raw = str(r.get("reason") or "").strip()

    if not problem or not solution:
        _prefix, paren_prob, tail = _extract_paren_problem(raw)
        if paren_prob and not problem:
            problem = paren_prob
        if tail and not solution:
            parsed_sol, _enc = _strip_encourage_from_tail(tail)
            if parsed_sol and not _looks_like_generic_advice(parsed_sol):
                solution = parsed_sol

    if not problem and raw and not raw.startswith("按评分标准"):
        if "（" not in raw and "）" not in raw:
            problem = raw[:55]

    if not problem:
        dim_note = str(rubric_row.get("dimension_reason") or "").strip()
        problem = _plain_strength_hint(label, dim_note) or f"符合「{label}」方向，仍可再具体化"

    if not solution or _looks_like_generic_advice(solution):
        solution = _infer_keep_solution_example(problem, quote, label)
    else:
        solution = _format_solution_example(solution)

    r["keep_problem"] = problem[:120]
    r["keep_solution"] = solution[:260]
    r["reason"] = _compose_keep_display_reason(label, problem)
    return r


def align_keep_segments_to_rubric(
    keep: list[dict[str, str]],
    rubric_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """将符合评分标准的亮点句标注出来，并生成鼓励式说明。"""
    if not keep:
        return keep
    if not rubric_rows:
        for idx, row in enumerate(keep):
            keep[idx] = _finalize_keep_segment_row(
                row,
                {"label": str(row.get("rubric_dimension_label") or "这一项"), "dimension_reason": ""},
            )
        return keep

    order = {str(r.get("id") or ""): i for i, r in enumerate(rubric_rows)}
    enriched: list[dict[str, str]] = []
    for idx, row in enumerate(keep):
        r = dict(row)
        r["_ord"] = str(idx)
        blob = f"{r.get('quote') or ''} {r.get('reason') or ''}"
        rid = str(r.get("rubric_dimension_id") or "").strip()
        if not rid:
            label = str(r.get("rubric_dimension_label") or "").strip()
            rid = next(
                (str(x.get("id") or "") for x in rubric_rows if label and label in str(x.get("label") or "")),
                "",
            )
        rubric = next((x for x in rubric_rows if str(x.get("id") or "") == rid), None)
        if rubric is None:
            rubric = max(rubric_rows, key=lambda x: _score_keep_for_rubric(blob, x))
        r["rubric_dimension_id"] = str(rubric.get("id") or "")
        r["rubric_dimension_label"] = str(rubric.get("label") or "")
        r["rubric_standard_note"] = str(rubric.get("dimension_reason") or "")[:200]
        r["encourage"] = True
        r = _finalize_keep_segment_row(r, rubric)
        enriched.append(r)

    enriched.sort(
        key=lambda r: (
            order.get(str(r.get("rubric_dimension_id") or ""), 999),
            int(r.get("_ord") or 0),
        )
    )
    for r in enriched:
        r.pop("_ord", None)
    return enriched[:8]


def _validate_keep_segments(content: str, segments: Any) -> list[dict[str, str]]:
    if not isinstance(segments, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[tuple[int, int]] = set()
    for row in segments:
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote") or "").strip()
        if len(quote) < 8:
            continue
        pos = content.find(quote)
        if pos < 0:
            continue
        span = (pos, pos + len(quote))
        if span in seen:
            continue
        seen.add(span)
        reason = str(row.get("reason") or "").strip()[:240]
        item: dict[str, str] = {"quote": quote, "reason": reason}
        kp = str(row.get("keep_problem") or "").strip()[:120]
        ks = str(row.get("keep_solution") or "").strip()[:260]
        if kp:
            item["keep_problem"] = kp
        if ks:
            item["keep_solution"] = ks
        rid = str(row.get("rubric_dimension_id") or "").strip()
        rlabel = str(row.get("rubric_dimension_label") or "").strip()
        if rid:
            item["rubric_dimension_id"] = rid
        if rlabel:
            item["rubric_dimension_label"] = rlabel
        out.append(item)
        if len(out) >= 8:
            break
    return out


def _infer_char_diff_chunks(
    original: str,
    rewrite: str,
    *,
    min_len: int = 6,
    max_items: int = 12,
) -> list[dict[str, str]]:
    """字符级 diff 的 insert/replace 区域，再切分为短片段，便于精确标红。"""
    max_one = _max_edit_quote_len(len(rewrite))
    matcher = difflib.SequenceMatcher(None, original, rewrite)
    raw: list[dict[str, str]] = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag not in ("replace", "insert"):
            continue
        pos = j1
        while pos < j2:
            chunk_end = min(j2, pos + max_one)
            if chunk_end < j2:
                sub = rewrite[pos:chunk_end]
                break_at = max(sub.rfind("，"), sub.rfind("、"), sub.rfind("。"), sub.rfind("；"))
                if break_at >= min_len:
                    chunk_end = pos + break_at + 1
            quote = rewrite[pos:chunk_end].strip()
            if len(quote) >= min_len and quote not in original:
                raw.append({"quote": quote, "reason": "相对原文调整"})
            pos = chunk_end if chunk_end > pos else pos + 1
    return _validate_quote_segments(
        rewrite,
        raw,
        min_len=min_len,
        max_items=max_items,
        max_quote_len=max_one,
    )


def _infer_keep_segments(original: str, rewrite: str, *, max_items: int = 8) -> list[dict[str, str]]:
    """原文中一字不差出现在改写文中的句子，作为保留片段（补全模型遗漏）。"""
    candidates: list[tuple[int, dict[str, str]]] = []
    for start, end in _iter_sentence_spans(original):
        quote = original[start:end]
        if len(quote) < 12:
            continue
        if quote not in rewrite:
            continue
        candidates.append(
            (
                len(quote),
                {
                    "quote": quote,
                    "reason": "这句话写得不错，符合评分要求。继续保持。",
                },
            )
        )
    candidates.sort(key=lambda x: x[0], reverse=True)
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for _ln, row in candidates:
        q = row["quote"]
        if q in seen:
            continue
        seen.add(q)
        out.append(row)
        if len(out) >= max_items:
            break
    return out


def _segments_to_spans(text: str, segments: list[dict[str, str]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for row in segments:
        quote = (row.get("quote") or "").strip()
        if not quote:
            continue
        pos = text.find(quote)
        if pos < 0:
            continue
        span = (pos, pos + len(quote))
        if span in seen:
            continue
        seen.add(span)
        spans.append(
            {
                "start": span[0],
                "end": span[1],
                "reason": row.get("reason") or "",
            }
        )
    spans.sort(key=lambda s: s["start"])
    return spans


def _trim_segments_by_coverage(rewrite: str, segments: list[dict[str, str]]) -> list[dict[str, str]]:
    if not segments:
        return []
    ordered = sorted(segments, key=lambda r: len(r.get("quote") or ""))
    kept: list[dict[str, str]] = []
    for row in ordered:
        kept.append(row)
        if _highlight_coverage(rewrite, kept) > _MAX_HIGHLIGHT_COVERAGE:
            kept.pop()
    kept.sort(key=lambda r: rewrite.find(r.get("quote") or ""))
    return kept[:8]


def _infer_edit_segments(original: str, rewrite: str, *, min_len: int = 8, max_items: int = 8) -> list[dict[str, str]]:
    """按句/分句对比原文，仅标出改写文中相对原文有变化的片段（避免整篇 replace 标红）。"""
    max_one = _max_edit_quote_len(len(rewrite))
    raw: list[dict[str, str]] = []
    for start, end in _iter_sentence_spans(rewrite):
        quote = rewrite[start:end]
        if len(quote) < min_len:
            continue
        if quote in original or _best_similarity_in_haystack(quote, original) >= 0.94:
            continue
        if len(quote) <= max_one:
            raw.append({"quote": quote, "reason": "相对原文调整"})
            continue
        for c_start, c_end in _iter_clause_spans(quote, start):
            clause = rewrite[c_start:c_end]
            if clause in original or _best_similarity_in_haystack(clause, original) >= 0.94:
                continue
            if len(clause) <= max_one:
                raw.append({"quote": clause, "reason": "相对原文调整"})
    return _validate_quote_segments(
        rewrite,
        raw,
        min_len=min_len,
        max_items=max_items,
        max_quote_len=max_one,
    )


def _refine_edit_segments(original: str, rewrite: str, segments: list[dict[str, str]]) -> list[dict[str, str]]:
    max_one = _max_edit_quote_len(len(rewrite))
    refined: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in segments:
        quote = (row.get("quote") or "").strip()
        if len(quote) < 8 or len(quote) > max_one:
            continue
        if quote in original or _best_similarity_in_haystack(quote, original) >= 0.94:
            continue
        if quote in seen:
            continue
        if rewrite.find(quote) < 0:
            continue
        seen.add(quote)
        refined.append({"quote": quote, "reason": row.get("reason") or "相对原文调整"})
    if _highlight_coverage(rewrite, refined) <= _MAX_HIGHLIGHT_COVERAGE:
        return refined[:8]
    return _trim_segments_by_coverage(rewrite, refined)


def _finalize_rewrite_display(
    original: str,
    rewrite: str,
    keep: list[dict[str, str]],
    edit: list[dict[str, str]],
    *,
    rubric_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not edit:
        edit = _infer_edit_segments(original, rewrite)
    if not edit:
        edit = _infer_char_diff_chunks(original, rewrite)
    edit = _refine_edit_segments(original, rewrite, edit)
    if not edit:
        edit = _trim_segments_by_coverage(rewrite, _infer_char_diff_chunks(original, rewrite, max_items=16))

    if len(keep) < 2:
        inferred_keep = _infer_keep_segments(original, rewrite)
        seen = {r["quote"] for r in keep}
        for row in inferred_keep:
            if row["quote"] not in seen:
                keep.append(row)
                seen.add(row["quote"])
            if len(keep) >= 8:
                break

    edit = _filter_edits_against_keep(edit, keep[:8])
    edit = _trim_segments_by_coverage(rewrite, edit)
    keep = align_keep_segments_to_rubric(keep[:8], rubric_rows or [])
    return {
        "keep_segments": keep,
        "edit_segments": edit,
        "keep_spans": _segments_to_spans(original, keep[:8]),
        "edit_spans": _segments_to_spans(rewrite, edit),
        "paragraph_count": len(_split_paragraphs(rewrite)),
    }


def refresh_rewrite_demo_display(
    demo: dict[str, Any],
    original: str,
    *,
    report_payload: dict[str, Any] | None = None,
) -> bool:
    """读报告时自愈：重算 spans / 裁剪高亮（不触发 LLM）。"""
    if not isinstance(demo, dict) or demo.get("status") != "ready":
        return False
    rewrite = str(demo.get("rewrite_text") or "").strip()
    if not rewrite or not original.strip():
        return False
    rewrite = format_rewrite_layout(original.strip(), rewrite)
    demo["rewrite_text"] = rewrite
    keep = demo.get("keep_segments")
    edit = demo.get("edit_segments")
    if not isinstance(keep, list):
        keep = []
    if not isinstance(edit, list):
        edit = []
    keep_rows = [r for r in keep if isinstance(r, dict)]
    edit_rows = [r for r in edit if isinstance(r, dict)]
    rubric_rows = collect_rubric_rows(report_payload or {})
    finalized = _finalize_rewrite_display(
        original.strip(),
        rewrite,
        keep_rows,
        edit_rows,
        rubric_rows=rubric_rows,
    )
    demo["keep_segments"] = finalized["keep_segments"]
    demo["edit_segments"] = finalized["edit_segments"]
    demo["keep_spans"] = finalized["keep_spans"]
    demo["edit_spans"] = finalized["edit_spans"]
    demo["paragraph_count"] = finalized.get("paragraph_count")
    demo["schema_version"] = REWRITE_DEMO_SCHEMA_VERSION
    return True


def _normalize_rewrite_payload(
    data: dict[str, Any],
    content: str,
    *,
    report_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rewrite_text = format_rewrite_layout(content, str(data.get("rewrite_text") or "").strip())
    rubric_rows = collect_rubric_rows(report_payload or {})
    summary_raw = data.get("change_summary")
    summary: list[str] = []
    if isinstance(summary_raw, list):
        summary = [str(s).strip() for s in summary_raw if str(s).strip()][:6]
    elif isinstance(summary_raw, str) and summary_raw.strip():
        summary = [summary_raw.strip()]
    keep = _validate_keep_segments(content, data.get("keep_segments"))
    keep = [row for row in keep if rewrite_text.find(row["quote"]) >= 0]
    max_one = _max_edit_quote_len(len(rewrite_text))
    edit = _validate_quote_segments(
        rewrite_text,
        data.get("edit_segments"),
        min_len=6,
        max_items=12,
        max_quote_len=max_one,
    )
    finalized = _finalize_rewrite_display(content, rewrite_text, keep, edit, rubric_rows=rubric_rows)
    similarity = difflib.SequenceMatcher(None, content, rewrite_text).ratio()
    warning = ""
    if similarity < 0.68:
        warning = "改写与原文差异偏大，更像重写而非局部修改；建议点击「重新生成」或对照建议自行微调。"
    if not finalized["edit_spans"]:
        warning = (warning + " " if warning else "") + "未能定位修改片段，请重新生成改写范例。"
    return {
        "rewrite_text": rewrite_text,
        "keep_segments": finalized["keep_segments"],
        "edit_segments": finalized["edit_segments"],
        "keep_spans": finalized["keep_spans"],
        "edit_spans": finalized["edit_spans"],
        "paragraph_count": finalized.get("paragraph_count"),
        "change_summary": summary,
        "minimal_edit_ratio": round(similarity, 3),
        "minimal_edit_warning": warning.strip() or None,
    }


async def generate_rewrite_demo_for_report(
    db: Session,
    *,
    report: Report,
    submission: Submission,
    question: Question | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    content = (submission.content or "").strip()
    if len(content) < 80:
        raise ValueError("ESSAY_TOO_SHORT")

    if payload.get("display_mode") == "reference_only":
        raise ValueError("REFERENCE_ONLY")

    ctx = resolve_essay_context(submission, question, db)
    material_excerpt = (ctx.reference_material or "")[:2500]
    user_input = {
        "essay_prompt": ctx.prompt[:4000],
        "reference_material_excerpt": material_excerpt,
        "student_essay": content[:12000],
        "issues": (payload.get("issues") or [])[:5],
        "suggestions": (payload.get("suggestions") or [])[:8],
        "scoring_points": (payload.get("scoring_points") or [])[:8],
        "scoring_rubric": collect_rubric_rows(payload),
        "review_notes": str(payload.get("review_notes") or "")[:800],
    }
    user_prompt = json.dumps(user_input, ensure_ascii=False)

    cred = get_credential(db, report.user_id, CredentialRole.primary)
    if not cred:
        raise AiCallError("NO_CREDENTIAL", "未配置主模型 API Key")

    raw, usage = await chat_completion_json(cred, REWRITE_DEMO_SYSTEM, user_prompt)
    log_usage(db, report.user_id, report.grading_job_id, cred, usage, "rewrite_demo")

    data = json.loads(raw)
    if not isinstance(data, dict):
        raise AiCallError("UPSTREAM", "改写范例返回非对象 JSON")

    normalized = _normalize_rewrite_payload(data, content, report_payload=payload)
    if not normalized["rewrite_text"]:
        raise AiCallError("UPSTREAM", "改写范例正文为空")

    demo = {
        "status": "ready",
        "schema_version": REWRITE_DEMO_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        **normalized,
    }
    return demo
