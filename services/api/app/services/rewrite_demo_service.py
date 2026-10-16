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
REWRITE_DEMO_SCHEMA_VERSION = 16

KEEP_SOLUTION_EXAMPLE_PREFIX = "续写示例，非对准问题，仅供参考："

MARKDOWN_BODY_INDENT = "\u3000\u3000"

# 单条 edit 与全文高亮占比上限，避免「全文标红」
_MAX_EDIT_SEGMENT_FRAC = 0.12
_MAX_HIGHLIGHT_COVERAGE = 0.28
_MIN_KEEP_SEGMENTS = 2
_MIN_EDIT_SEGMENTS = 1
_MIN_REWRITE_SIMILARITY = 0.68
_REGENERATE_MAX_ATTEMPTS = 3

REWRITE_DEMO_SYSTEM = """你是申论大作文写作教练。任务是在用户原文基础上做「局部润色与补改」，不是重写一篇新作文。
硬性要求：
1. rewrite_text 必须以 student_essay 为底稿：保留原文结构、标题（若有）、段落顺序与核心立意；局部修改的唯一依据是 primary_issues（评分中的主要问题，含 user_quote），不得脱离这些问题另改无关句子。
2. 全文被改写的字符量（相对原文的新增、替换、删除合计）不得超过约 30%；禁止整段另写、换题、换论证主线。
3. keep_segments（标准亮点句）：从 student_essay 中挑出 3～8 句「符合 scoring_rubric、写得特别好」的原文（quote 为连续子串，且须原封不动出现在 rewrite_text）；每条绑定一个 rubric 维度。须同时给出 keep_problem（该句仍存在的不足/风险，15～55 字，写入展示括号内）与 keep_solution（针对 keep_problem 的示范写法：1～2 句可直接借鉴的示例文字，可紧接原句续写或略作改写，25～100 字；必须是「怎么写」的例句，禁止「补写分析」「强化论证」等空泛指导）。reason 可省略（由系统合成）。
4. edit_segments：2～8 条，quote 必须是 rewrite_text 的连续子串，且只能是「改过的一小句/短语」（8～80 字）；禁止把整段、整节或全文作为一条 quote；与原文完全相同的句子不得列入。
   每条 edit 必须对应 primary_issues 中的一条：issue_tag 与 source_quote 必填；quote 须落在 source_quote 所在语句内，改写后 source_quote 不得整段原封不动出现在 rewrite_text 中。
   primary_issues 中每条须至少有一条 edit 与之对应；禁止只改与问题无关的句子。
5. change_summary：2～4 条，逐条对应主要问题的改法，勿写「全文重写」类表述。
6. 改写须紧扣 source_quote 所在句的具体表述微调，禁止用与原文无关的提纲套话（如原文未写「问题诊断」「机制创新」等，勿强行塞入）。
7. 排版（Markdown 范文）：与 student_essay 换行、空行一致；除标题行外，每个段落首行必须以两个全角空格「　　」开头；标题行不缩进、不居中。
仅输出 JSON：
{
  "rewrite_text": string,
  "keep_segments": [{"quote": string, "keep_problem": string, "keep_solution": string, "reason": string, "rubric_dimension_id": string, "rubric_dimension_label": string}],
  "edit_segments": [{"quote": string, "reason": string, "issue_tag": string, "source_quote": string}],
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
    if not t:
        return False
    if re.match(r"^#{1,6}\s+\S", t):
        return True
    return len(t) <= 48 and not re.search(r"[。！？；]", t)


def _title_line_plain(line: str) -> str:
    return re.sub(r"^#{1,6}\s+", "", line.strip())


def _first_title_line_index(lines: list[str]) -> int | None:
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        if _is_title_line(line) and not _line_leading_indent(line):
            return idx
        break
    return None


def preserve_title_from_reference(reference: str, text: str) -> str:
    """
    若参考作答首行是标题而 text 中缺失，补回标题行（避免改写/重作后标题丢失）。
    若 text 首段已是另一行合法标题，则保留模型自拟标题。
    """
    ref_lines = _normalize_newlines(reference).split("\n")
    title_at = _first_title_line_index(ref_lines)
    if title_at is None:
        return text

    title_line = ref_lines[title_at]
    title_plain = _title_line_plain(title_line)
    rw = _normalize_newlines(text).strip()
    if not rw:
        return text

    head = "\n".join(rw_lines := rw.split("\n"))[:120]
    if title_plain and title_plain in head:
        first_nonempty = next((ln for ln in rw_lines if ln.strip()), "")
        if title_plain in first_nonempty or _is_title_line(first_nonempty):
            return text

    rw_lines = rw.split("\n")
    first_content = next((ln for ln in rw_lines if ln.strip()), "")
    if first_content and _is_title_line(first_content) and not _line_leading_indent(first_content):
        first_plain = _title_line_plain(first_content)
        if first_plain and first_plain != title_plain:
            return text

    prefix = [title_line.rstrip()]
    if title_at + 1 < len(ref_lines) and not ref_lines[title_at + 1].strip():
        prefix.append("")
    return "\n".join(prefix) + rw


def _restore_title_slots(reference: str, text: str) -> str:
    """镜像行结构后，把被正文挤占的标题行槽位还原为参考标题。"""
    ref_lines = _normalize_newlines(reference).split("\n")
    out_lines = _normalize_newlines(text).split("\n")
    while len(out_lines) < len(ref_lines):
        out_lines.append("")

    for idx, ref_line in enumerate(ref_lines):
        if not ref_line.strip():
            continue
        if not _is_title_line(ref_line) or _line_leading_indent(ref_line):
            continue
        if idx >= len(out_lines):
            out_lines.insert(idx, ref_line)
            continue
        cur = out_lines[idx]
        if not cur.strip():
            out_lines[idx] = ref_line
            continue
        if not _is_title_line(cur) or _line_leading_indent(cur):
            out_lines[idx] = ref_line
    return "\n".join(out_lines)


def _atx_heading_prefix(line: str) -> str:
    m = re.match(r"^(#{1,6}\s+)", line.strip())
    return m.group(1) if m else ""


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
            prefix = _atx_heading_prefix(orig) if orig.strip() else _atx_heading_prefix(line)
            body = re.sub(r"^#{1,6}\s+", "", stripped)
            out.append(f"{prefix}{body}" if prefix else stripped)
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
    rewrite = preserve_title_from_reference(original, rewrite)
    mirrored = mirror_original_line_layout(original, rewrite)
    mirrored = _restore_title_slots(original, mirrored)
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
        kept: dict[str, str] = {"quote": quote, "reason": reason}
        issue_tag = str(row.get("issue_tag") or "").strip()[:80]
        source_quote = str(row.get("source_quote") or "").strip()[:240]
        if issue_tag:
            kept["issue_tag"] = issue_tag
        if source_quote:
            kept["source_quote"] = source_quote
        out.append(kept)
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


_GENERIC_SOLUTION_MARKERS = (
    "精细治理",
    "听得到诉求",
    "看得见变化",
    "管得住风险",
    "网格议事",
    "以某县",
    "以某社区",
    "王弼所谓",
    "源头活水",
)


def _solution_example_relates_to_issue(text: str, issue: dict[str, Any], original: str = "") -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    quote = str(issue.get("user_quote") or "").strip()
    prob = str(issue.get("explanation") or issue.get("issue_title") or "").strip()
    inner = raw
    m = re.search(r"[「]([^」]{4,})[」]", raw)
    if m:
        inner = m.group(1)
    else:
        inner = re.sub(r"^改写示例[：:]\s*", "", raw).strip("「」")

    if any(g in raw for g in _GENERIC_SOLUTION_MARKERS):
        if quote and not any(g in quote for g in _GENERIC_SOLUTION_MARKERS):
            if not prob or not any(g in prob for g in _GENERIC_SOLUTION_MARKERS):
                return False

    if len(quote) < 8:
        return True

    if difflib.SequenceMatcher(None, quote, inner).ratio() >= 0.08:
        return True
    for n in range(min(len(quote), 52), 5, -2):
        sub = quote[:n]
        if sub in inner or sub in raw:
            return True
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", quote):
        if len(run) >= 3 and (run in inner or run in raw):
            return True
    for run in re.findall(r"[\u4e00-\u9fff]{3,}", prob):
        if run in inner:
            return True
    if original and quote:
        loc = _locate_quote_span(original, quote)
        if loc and inner and inner in original[loc[0] : loc[1]]:
            return True
        if loc and inner and difflib.SequenceMatcher(None, quote, inner).ratio() < 0.12:
            for n in range(min(len(quote), 48), 5, -2):
                if quote[:n] in inner:
                    return True
            return False
    return False


def _extract_parallel_roles(q: str) -> list[str]:
    m = re.search(r"无论(.+?)还是(.+?)，", q)
    if not m:
        return []
    left, right = m.group(1), m.group(2)
    roles = [x.strip() for x in re.split(r"[、,，]", left) if x.strip()]
    if right.strip():
        roles.append(right.strip())
    return roles


def _pack_concrete_example(new_text: str, _old_quote: str = "") -> str:
    new_text = (new_text or "").strip()
    if not new_text:
        return ""
    body = _trim_new_body(new_text, max_len=220)
    return f"改写示例：「{body}」"


def _concrete_rewrite_for_repeat(q: str) -> str:
    roles = _extract_parallel_roles(q)
    if len(roles) >= 3:
        return (
            f"{roles[0]}在技艺上精益求精，{roles[1]}在一线补齐短板，{roles[2]}在本职上久久为功；"
            "三者同向发力，把专注与坚守汇成可感的生活秩序。"
        )
    if len(roles) == 2:
        return (
            f"{roles[0]}侧重打磨精度，{roles[1]}侧重修补漏洞；"
            "本段用一句因果分析收束，并与上段案例形成递进。"
        )
    fillers = (
        "无论",
        "都应摒弃急功近利心态，",
        "把自己的领域当作耕耘的田野，",
        "以久久为功的专注",
        "让默默付出汇成",
    )
    s = q
    for ph in fillers:
        s = s.replace(ph, "")
    s = re.sub(r"[，,\s]{2,}", "，", s).strip("，。； ")
    if len(s) >= 18:
        return f"{s.rstrip('，。；')}，并归结到可感的生活秩序。"
    return "工匠、干部与从业者各就其位：精益求精、补齐短板、久久为功，共同托举温暖笃定的生活秩序。"


def _concrete_rewrite_format(q: str) -> str:
    out = re.sub(r"^\s*3\.\s*", "", q)
    out = re.sub(r"(?<=[。；])\s*3\.\s*", "", out)
    return out.strip()


def _concrete_rewrite_template(q: str, prob: str) -> str | None:
    m = re.search(r"[「『]([^」』]{4,36})[」』]", prob)
    bad = m.group(1).strip() if m else ""
    if bad and bad in q:
        return q.replace(bad, "从而托举温暖笃定、可持续的生活秩序")
    replacements = (
        ("方能共建温暖、安定、美好的生活家园", "从而托举温暖笃定的生活秩序"),
        ("共建温暖、安定、美好的生活家园", "让生活秩序更可感、更可持续"),
        ("美好家园", "可感的生活秩序"),
    )
    out = q
    for a, b in replacements:
        if a in out:
            out = out.replace(a, b)
    if out != q:
        return out
    if "模版" in prob or "模板" in prob or "模版化" in prob:
        if q.endswith("笃定") or "笃定" in q[-12:]:
            return re.sub(r"让默默付出汇成生活的笃定$", "让默默付出转化为可检验的生活秩序", q)
    return None


def _concrete_rewrite_light_polish(q: str) -> str | None:
    out = _concrete_rewrite_format(q)
    out = re.sub(r"，{2,}", "，", out)
    if out != q:
        return out
    parts = re.split(r"(?<=[。；])", q)
    if len(parts) >= 2 and len(q) > 72:
        head = "".join(parts[:-1]).strip()
        tail = parts[-1].strip()
        tail = re.sub(r"^(从而|因此|所以)", "由此", tail)
        if head and tail:
            return f"{head}{tail}"
    return None


def _is_language_style_issue(prob: str, label: str) -> bool:
    p = prob or ""
    lab = label or ""
    if "语言" in lab or "语言" in p or "表达" in p or "规范性" in p:
        return True
    return bool(
        re.search(r"3\.\s*|误输入|格式残留|格式错误", p)
        or any(x in p for x in ("模版", "模板", "套话", "口号", "模版化"))
    )


def _rewrite_snippet_in_essay(original: str, prob: str) -> str | None:
    """说明里点名的套话/误输若在正文其它位置，给出该句改写。"""
    if not original.strip():
        return None
    m = re.search(r"[「『]([^」』]{4,40})[」』]", prob)
    bad = m.group(1).strip() if m else ""
    if bad and bad in original:
        pos = original.find(bad)
        sent = _sentence_at(original, pos)
        if sent and bad in sent:
            return sent.replace(bad, "从而托举温暖笃定的生活秩序")
    for phrase, repl in (
        ("方能共建温暖、安定、美好的生活家园", "从而托举温暖笃定的生活秩序"),
        ("共建温暖、安定、美好的生活家园", "让生活秩序更可感、更可持续"),
    ):
        if phrase in original:
            pos = original.find(phrase)
            sent = _sentence_at(original, pos)
            if sent and phrase in sent:
                return sent.replace(phrase, repl)
    if re.search(r"3\.\s*|误输入|格式", prob):
        m3 = re.search(r"(?:^|[\n\r])\s*3\.\s*[^\n\r。！？]{4,}", original)
        if m3:
            sent = m3.group(0).strip()
            fixed = re.sub(r"^\s*3\.\s*", "", sent)
            if fixed and fixed != sent:
                return fixed
    return None


def _concrete_rewrite_language_quote(q: str, prob: str) -> str:
    s = _concrete_rewrite_format(q).strip()
    s = re.sub(r"，{2,}", "，", s)
    for old, new in (
        ("这一领域，", ""),
        ("针对", "面向"),
        ("让群众在家门口就能看病", "使群众就近可及就医"),
        ("；正说明", "，可见"),
        ("正说明", "可见"),
        ("等政策，", "等举措，"),
    ):
        if old in s:
            s = s.replace(old, new)
    s = s.strip("，； ")
    if s and not s.endswith("。"):
        s += "。"
    if s == q or s == q + "。":
        if "；" in q:
            s = q.replace("；", "，", 1)
        elif "这一" in q:
            s = q.replace("这一", "该", 1)
        else:
            s = f"{q.rstrip('。；，')}。"
    return _trim_new_body(s, max_len=220)


def _infer_issue_solution_from_context(
    prob: str,
    quote: str,
    label: str,
    original: str = "",
) -> str | None:
    """二次批改轻微问题：给出可落地的改写句（非空泛写作建议）。"""
    p = (prob or "").strip()
    q = (quote or "").strip().strip("「」")
    lab = (label or "").strip()
    orig = (original or "").strip()

    if "重复" in p or "重复" in lab or "递进" in p:
        if q:
            return _pack_concrete_example(_concrete_rewrite_for_repeat(q), q)

    if _is_language_style_issue(p, lab):
        if orig:
            from app.services.grading_helpers import resolve_issue_anchor_from_explanation

            anchor_issue = {"explanation": p, "issue_title": lab}
            target = resolve_issue_anchor_from_explanation(orig, anchor_issue).strip("「」")
            if target:
                templ = _concrete_rewrite_template(target, p)
                rewritten = templ or _concrete_rewrite_format(target)
                if not rewritten or rewritten == target:
                    rewritten = _concrete_rewrite_language_quote(target, p)
                return _pack_concrete_example(rewritten, target)
            from_essay = _rewrite_snippet_in_essay(orig, p)
            if from_essay:
                return _pack_concrete_example(from_essay, from_essay)
        if q:
            m = re.search(r"[「『]([^」』]{4,40})[」』]", p)
            bad = m.group(1).strip() if m else ""
            if bad and bad in q:
                return _pack_concrete_example(
                    q.replace(bad, "从而托举温暖笃定的生活秩序"),
                    q,
                )
            templ = _concrete_rewrite_template(q, p)
            if templ and templ != q:
                return _pack_concrete_example(templ, q)
            fixed = _concrete_rewrite_format(q)
            if fixed and fixed != q:
                return _pack_concrete_example(fixed, q)
            return _pack_concrete_example(_concrete_rewrite_language_quote(q, p), q)

    if len(q) >= 16:
        polished = _concrete_rewrite_light_polish(q)
        if polished and polished != q:
            return _pack_concrete_example(polished, q)

    if not q:
        return _infer_keep_solution_example(p, q, lab)
    return None


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


def _clip_source_quote(text: str, *, max_len: int = 160) -> str:
    t = text.strip()
    if len(t) <= max_len:
        return t
    for sep in ("。", "！", "？", "；"):
        idx = t.rfind(sep, 0, max_len)
        if idx >= 12:
            return t[: idx + 1]
    return t[: max_len - 1] + "…"


def _infer_source_quote_from_diff(original: str, rewrite: str, edit_quote: str) -> str:
    quote = edit_quote.strip()
    if len(quote) < 4:
        return ""
    pos = rewrite.find(quote)
    if pos < 0:
        return ""
    anchor = pos + len(quote) // 2
    matcher = difflib.SequenceMatcher(None, original, rewrite)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if anchor < j1 or pos >= j2:
            continue
        if tag == "replace" and i2 > i1:
            chunk = original[i1:i2].strip()
            if len(chunk) >= 4:
                return _clip_source_quote(chunk)
        if tag == "insert":
            sent = _sentence_at(original, max(0, min(len(original) - 1, i1)))
            if sent.strip():
                return _clip_source_quote(sent)
    ratio = pos / max(len(rewrite), 1)
    approx = min(len(original) - 1, int(ratio * len(original)))
    sent = _sentence_at(original, approx)
    return _clip_source_quote(sent) if sent.strip() else ""


def _enrich_edit_segment_sources(
    original: str,
    rewrite: str,
    edits: list[dict[str, str]],
    primary_issues: list[dict[str, Any]] | None,
) -> None:
    """补全 source_quote / issue_tag，供左右对照高亮与问题落实校验。"""
    issues = primary_issues or []
    for row in edits:
        sq = str(row.get("source_quote") or "").strip()
        if sq and original.find(sq) >= 0:
            continue
        tag = str(row.get("issue_tag") or "").strip()
        if tag:
            for issue in issues:
                if _edit_matches_issue_tag({"issue_tag": tag, "reason": row.get("reason")}, issue):
                    uq = str(issue.get("user_quote") or "").strip()
                    if uq and original.find(uq) >= 0:
                        row["source_quote"] = _clip_source_quote(uq)
                        break
        sq = str(row.get("source_quote") or "").strip()
        if sq and original.find(sq) >= 0:
            continue
        eq = str(row.get("quote") or "").strip()
        inferred = _infer_source_quote_from_diff(original, rewrite, eq)
        if inferred and original.find(inferred) >= 0:
            row["source_quote"] = inferred
            continue
        if not tag and issues:
            for issue in issues:
                uq = str(issue.get("user_quote") or "").strip()
                if not uq or original.find(uq) < 0:
                    continue
                span = _locate_quote_span(original, uq)
                if span is None:
                    continue
                epos = rewrite.find(eq) if eq else -1
                if epos < 0:
                    continue
                ratio_e = epos / max(len(rewrite), 1)
                ratio_o = span[0] / max(len(original), 1)
                if abs(ratio_e - ratio_o) <= 0.22:
                    row["source_quote"] = _clip_source_quote(uq)
                    row.setdefault("issue_tag", str(issue.get("tag") or "").strip()[:80])
                    break


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
        kept: dict[str, str] = {"quote": quote, "reason": str(row.get("reason") or "相对原文调整")}
        issue_tag = str(row.get("issue_tag") or "").strip()[:80]
        source_quote = str(row.get("source_quote") or "").strip()[:240]
        if issue_tag:
            kept["issue_tag"] = issue_tag
        if source_quote:
            kept["source_quote"] = source_quote
        refined.append(kept)
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
    primary_issues: list[dict[str, Any]] | None = None,
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
    _enrich_edit_segment_sources(original, rewrite, edit, primary_issues)
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
    payload = dict(report_payload or {})
    from app.services.grading_helpers import enrich_report_essay_quotes

    enrich_report_essay_quotes(payload, original.strip())
    primary = collect_primary_issues(payload, for_rewrite_demo=True)
    finalized = _finalize_rewrite_display(
        original.strip(),
        rewrite,
        keep_rows,
        edit_rows,
        rubric_rows=rubric_rows,
        primary_issues=primary,
    )
    demo["keep_segments"] = finalized["keep_segments"]
    demo["edit_segments"] = finalized["edit_segments"]
    demo["keep_spans"] = finalized["keep_spans"]
    demo["edit_spans"] = finalized["edit_spans"]
    demo["paragraph_count"] = finalized.get("paragraph_count")
    demo["schema_version"] = REWRITE_DEMO_SCHEMA_VERSION
    if primary:
        issue_errors = validate_rewrite_covers_primary_issues(
            original.strip(), rewrite, demo, primary
        )
        fix_status = build_issue_fix_status(original.strip(), rewrite, demo, primary)
        prev = demo.get("validation_check") if isinstance(demo.get("validation_check"), dict) else {}
        demo["validation_check"] = {
            **prev,
            "issue_fix_status": fix_status,
            "issues_addressed": len(issue_errors) == 0,
            "errors": issue_errors or prev.get("errors") or [],
            "passed": bool(prev.get("passed")) and len(issue_errors) == 0,
        }
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
    primary = collect_primary_issues(report_payload or {})
    finalized = _finalize_rewrite_display(
        content,
        rewrite_text,
        keep,
        edit,
        rubric_rows=rubric_rows,
        primary_issues=primary,
    )
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


def is_second_pass_report(payload: dict[str, Any]) -> bool:
    try:
        return int(payload.get("attempt") or 1) >= 2
    except (TypeError, ValueError):
        return False


def rewrite_demo_allowed_for_payload(payload: dict[str, Any]) -> bool:
    """首稿可生成改写对照；重作后仅当存在「待继续改进」中等及以上问题时开放。"""
    if not is_second_pass_report(payload):
        return True
    block = payload.get("retry_major_issues")
    return isinstance(block, list) and len(block) > 0


def collect_primary_issues(
    payload: dict[str, Any],
    *,
    for_rewrite_demo: bool = False,
) -> list[dict[str, Any]]:
    """局部改写依据。重作后生成改写范例时仅含 retry_major_issues。"""
    if for_rewrite_demo and is_second_pass_report(payload):
        keys: tuple[str, ...] = ("retry_major_issues",)
    else:
        keys = ("issues", "retry_major_issues")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in keys:
        block = payload.get(key)
        if not isinstance(block, list):
            continue
        for item in block:
            if not isinstance(item, dict):
                continue
            tag = str(item.get("tag") or item.get("issue_title") or "").strip()
            quote = str(item.get("user_quote") or "").strip()
            dedupe = f"{tag}|{quote[:48]}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            out.append(
                {
                    "tag": tag,
                    "severity": item.get("severity"),
                    "explanation": str(item.get("explanation") or "").strip()[:400],
                    "user_quote": quote[:240],
                }
            )
    return out[:8]


def _collapse_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _locate_quote_span(text: str, quote: str) -> tuple[int, int] | None:
    q = quote.strip()
    if len(q) < 6:
        return None
    idx = text.find(q)
    if idx >= 0:
        return idx, idx + len(q)
    collapsed = _collapse_spaces(text)
    cq = _collapse_spaces(q)
    if len(cq) >= 6:
        cidx = collapsed.find(cq)
        if cidx >= 0:
            raw = 0
            col = 0
            while col < cidx and raw < len(text):
                if not text[raw].isspace():
                    col += 1
                raw += 1
            end_raw = raw
            col_end = 0
            while col_end < len(cq) and end_raw < len(text):
                if not text[end_raw].isspace():
                    col_end += 1
                end_raw += 1
            return raw, end_raw
    for length in range(min(len(q), 56), 7, -2):
        sub = q[:length]
        idx = text.find(sub)
        if idx >= 0:
            return idx, idx + len(sub)
    return None


def _edit_reason_matches_issue(row: dict[str, Any], issue: dict[str, Any]) -> bool:
    reason = str(row.get("reason") or "")
    tag = str(issue.get("tag") or "")
    if not reason or not tag:
        return False
    m = re.match(r"(Q\d+)", tag, re.I)
    if m and m.group(1).upper() in reason.upper():
        return True
    label = tag.split(maxsplit=1)[-1] if tag else ""
    return bool(label and len(label) >= 2 and label in reason)


def _edit_matches_issue_tag(row: dict[str, Any], issue: dict[str, Any]) -> bool:
    itag = str(row.get("issue_tag") or "").strip()
    tag = str(issue.get("tag") or "").strip()
    if itag and tag and (itag == tag or tag.startswith(itag) or itag.startswith(tag.split()[0])):
        return True
    return _edit_reason_matches_issue(row, issue)


def issue_addressed_by_rewrite(
    original: str,
    rewrite: str,
    edits: list[dict[str, Any]],
    issue: dict[str, Any],
) -> bool:
    quote = str(issue.get("user_quote") or "").strip()
    if not quote:
        for row in edits:
            if _edit_matches_issue_tag(row, issue):
                return True
        return False

    span = _locate_quote_span(original, quote)
    if span is None:
        return False
    start, end = span
    anchor = original[start:end]

    if anchor not in rewrite:
        return True

    rpos = rewrite.find(anchor)
    if rpos < 0:
        return True

    r_end = rpos + len(anchor)
    for row in edits:
        if not _edit_matches_issue_tag(row, issue):
            continue
        eq = str(row.get("quote") or "").strip()
        if not eq:
            continue
        epos = rewrite.find(eq)
        if epos < 0:
            continue
        e_end = epos + len(eq)
        if epos > r_end + 8 or e_end < rpos - 8:
            continue
        if eq not in original:
            return True
        opos = original.find(eq)
        if opos < 0:
            return True
        if original[opos : opos + len(eq)] != rewrite[epos : epos + len(eq)]:
            return True
    return False


def build_issue_fix_status(
    original: str,
    rewrite: str,
    demo: dict[str, Any],
    primary_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    edits = [r for r in (demo.get("edit_segments") or []) if isinstance(r, dict)]
    rows: list[dict[str, Any]] = []
    for idx, issue in enumerate(primary_issues):
        tag = str(issue.get("tag") or "").strip()
        quote = str(issue.get("user_quote") or "").strip()
        fixed = issue_addressed_by_rewrite(original, rewrite, edits, issue)
        linked: list[int] = []
        span = _locate_quote_span(original, quote) if quote else None
        if span:
            start, end = span
            anchor = original[start:end]
            rpos = rewrite.find(anchor) if anchor in rewrite else -1
            r_end = rpos + len(anchor) if rpos >= 0 else -1
            for ei, row in enumerate(edits):
                eq = str(row.get("quote") or "").strip()
                if not eq:
                    continue
                epos = rewrite.find(eq)
                if epos < 0:
                    continue
                e_end = epos + len(eq)
                if rpos >= 0 and epos <= r_end + 8 and e_end >= rpos - 8:
                    linked.append(ei + 1)
        rows.append(
            {
                "index": idx + 1,
                "tag": tag,
                "explanation": str(issue.get("explanation") or "")[:200],
                "user_quote": quote[:240],
                "fixed": fixed,
                "edit_indexes": linked,
            }
        )
    return rows


def _sentence_at(text: str, pos: int) -> str:
    pos = max(0, min(len(text), pos))
    left = text.rfind("。", 0, pos)
    left = max(left, text.rfind("！", 0, pos))
    left = max(left, text.rfind("？", 0, pos))
    start = 0 if left < 0 else left + 1
    right_candidates = [text.find(ch, pos) for ch in "。！？\n"]
    right_candidates = [x for x in right_candidates if x >= 0]
    end = min(right_candidates) + 1 if right_candidates else len(text)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _extract_change_fragments(old_text: str, new_text: str, *, min_len: int = 2) -> tuple[list[str], list[str]]:
    old_norm = re.sub(r"\s+", " ", (old_text or "").strip())
    new_norm = re.sub(r"\s+", " ", (new_text or "").strip())
    if not new_norm:
        return [], []
    matcher = difflib.SequenceMatcher(None, old_norm, new_norm)
    olds: list[str] = []
    news: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("replace", "delete"):
            seg = old_norm[i1:i2].strip("，、；： ")
            if len(seg) >= min_len:
                olds.append(seg)
        if tag in ("replace", "insert"):
            seg = new_norm[j1:j2].strip("，、；： ")
            if len(seg) >= min_len:
                news.append(seg)
    return news, olds


def _trim_new_body(new_body: str, *, max_len: int = 72) -> str:
    body = new_body.strip()
    if len(body) <= max_len:
        return body
    cut = body[:max_len]
    for sep in ("，", "、", "；", "。"):
        idx = cut.rfind(sep)
        if idx >= 12:
            return cut[: idx + 1] + "…"
    return cut + "…"


def _format_compact_rewrite_example(new_parts: list[str], old_parts: list[str]) -> str:
    news = [p for p in new_parts if p][:4]
    if not news:
        return ""
    if len(news) == 1 and len(news[0]) > 80 and not old_parts:
        first_clause = re.split(r"[，；。]", news[0], maxsplit=1)[0].strip()
        if len(first_clause) >= 8:
            news = [first_clause + ("…" if len(news[0]) > len(first_clause) else "")]
    new_body = _trim_new_body(" ".join(news))
    line = f"改写示例：「{new_body}」"
    olds = [p for p in old_parts if p][:3]
    if olds:
        old_body = " ".join(olds)
        if len(old_body) > 60:
            old_body = old_body[:57] + "…"
        line += f"\n（原：{old_body}）"
    return line


def _mark_spans_for_old_parts(
    original: str,
    old_parts: list[str],
    *,
    hint: tuple[int, int] | None,
) -> list[dict[str, int]]:
    spans: list[dict[str, int]] = []
    seen: set[tuple[int, int]] = set()
    win_lo = max(0, hint[0] - 64) if hint else 0
    win_hi = min(len(original), hint[1] + 64) if hint else len(original)
    for frag in old_parts:
        if len(frag) < 2:
            continue
        pos = original.find(frag, win_lo, win_hi)
        if pos < 0:
            pos = original.find(frag)
        if pos >= 0:
            span = (pos, pos + len(frag))
            if span not in seen:
                seen.add(span)
                spans.append({"start": span[0], "end": span[1]})
    return spans


def _solution_from_edit_row(
    row: dict[str, Any],
    original: str,
    issue: dict[str, Any],
) -> tuple[str | None, list[dict[str, int]]]:
    rewrite_q = str(row.get("quote") or "").strip()
    if len(rewrite_q) < 4:
        return None, []
    source = str(row.get("source_quote") or issue.get("user_quote") or "").strip()
    hint = _locate_quote_span(original, source) if source else None
    old_snip = original[hint[0] : hint[1]] if hint else source
    text = _pack_concrete_example(rewrite_q, source)
    spans: list[dict[str, int]] = []
    if hint:
        spans = [{"start": hint[0], "end": hint[1]}]
    elif old_snip:
        spans = _mark_spans_for_old_parts(original, [old_snip], hint=hint)
    return (text if text else None), spans


def _rewrite_example_near_quote(
    original: str,
    rewrite: str,
    quote: str,
) -> tuple[str | None, list[dict[str, int]]]:
    span = _locate_quote_span(original, quote)
    if not span:
        return None, []
    start, _end = span
    anchor = original[start : span[1]]
    rpos = rewrite.find(anchor) if anchor in rewrite else -1
    if rpos < 0:
        prefix = original[max(0, start - 24) : start]
        pi = rewrite.find(prefix) if prefix else -1
        if pi < 0:
            return None, []
        rs = pi + len(prefix)
        o_sent = _sentence_at(original, start)
        r_sent = _sentence_at(rewrite, rs)
    else:
        o_sent = _sentence_at(original, start)
        r_sent = _sentence_at(rewrite, rpos)
    if not o_sent or not r_sent or o_sent == r_sent:
        return None, []
    text = _pack_concrete_example(r_sent, o_sent)
    if not text:
        return None, []
    spans = _mark_spans_for_old_parts(original, [o_sent], hint=span)
    return text, spans


def _shrink_solution_example_text(
    text: str,
    original: str,
    issue: dict[str, Any],
) -> tuple[str, list[dict[str, int]]]:
    """过长「改写示例」压成 diff 片段，并返回原文标红区间。"""
    raw = (text or "").strip()
    if not raw:
        return text, []
    m = re.search(r"[「]([^」]{20,})[」]", raw)
    if not m:
        return text, []
    inner = m.group(1).strip()
    if len(inner) <= 88:
        return text, []
    quote = str(issue.get("user_quote") or "").strip()
    hint = _locate_quote_span(original, quote) if quote else None
    old_snip = original[hint[0] : hint[1]] if hint else quote
    base = old_snip or quote
    compact = _pack_concrete_example(inner, base)
    spans: list[dict[str, int]] = []
    if hint:
        spans = [{"start": hint[0], "end": hint[1]}]
    elif base:
        spans = _mark_spans_for_old_parts(original, [base], hint=hint)
    return compact, spans


def _compact_suggestion_example(
    original: str,
    issue: dict[str, Any],
    sug: str,
) -> tuple[str | None, list[dict[str, int]]]:
    sug = (sug or "").strip()
    if len(sug) < 8:
        return None, []
    quote = str(issue.get("user_quote") or "").strip()
    hint = _locate_quote_span(original, quote) if quote else None
    old_snip = original[hint[0] : hint[1]] if hint else quote
    inner = sug
    gm = re.search(r"[「]([^」]+)[」]", sug)
    if gm:
        inner = gm.group(1).strip()
    if len(inner) >= 12:
        compact = _pack_concrete_example(inner, old_snip or quote)
        spans = _mark_spans_for_old_parts(original, [old_snip] if old_snip else [], hint=hint)
        if not spans and hint:
            spans = [{"start": hint[0], "end": hint[1]}]
        return compact, spans
    if len(sug) <= 220:
        line = _pack_concrete_example(sug.strip("改写示例："), old_snip or quote)
        return line, []
    return None, []


def solution_example_for_issue(
    original: str,
    rewrite: str,
    issue: dict[str, Any],
    edits: list[dict[str, Any]],
    suggestions: list[Any],
    suggestion_index: int,
    *,
    use_rewrite_demo: bool = True,
) -> str | None:
    issue.pop("rewrite_mark_spans", None)

    quote = str(issue.get("user_quote") or "").strip()
    span = _locate_quote_span(original, quote) if quote else None
    r_start = r_end = -1
    if span:
        anchor = original[span[0] : span[1]]
        rpos = rewrite.find(anchor) if anchor in rewrite else -1
        if rpos >= 0:
            r_start, r_end = rpos, rpos + len(anchor)

    for row in edits:
        if not isinstance(row, dict):
            continue
        if not _edit_matches_issue_tag(row, issue):
            continue
        text, spans = _solution_from_edit_row(row, original, issue)
        if text:
            if spans:
                issue["rewrite_mark_spans"] = spans
            return text

    for row in edits:
        if not isinstance(row, dict):
            continue
        eq = str(row.get("quote") or "").strip()
        if len(eq) < 4:
            continue
        epos = rewrite.find(eq)
        if epos < 0:
            continue
        e_end = epos + len(eq)
        if span and r_start >= 0 and epos <= r_end + 12 and e_end >= r_start - 12:
            text, spans = _solution_from_edit_row(row, original, issue)
            if text:
                if spans:
                    issue["rewrite_mark_spans"] = spans
                return text

    if use_rewrite_demo and quote and rewrite:
        near, spans = _rewrite_example_near_quote(original, rewrite, quote)
        if near:
            if spans:
                issue["rewrite_mark_spans"] = spans
            return near

    if 0 <= suggestion_index < len(suggestions):
        sug = str(suggestions[suggestion_index] or "").strip()
        compact, spans = _compact_suggestion_example(original, issue, sug)
        if compact:
            if spans:
                issue["rewrite_mark_spans"] = spans
            return compact

    return None


def _finalize_solution_example(
    text: str,
    original: str,
    issue: dict[str, Any],
) -> str | None:
    if not text:
        return None
    shrunk, spans = _shrink_solution_example_text(text, original, issue)
    if spans and not issue.get("rewrite_mark_spans"):
        issue["rewrite_mark_spans"] = spans
    return shrunk


def _edit_matches_issue_tag(row: dict[str, Any], issue: dict[str, Any]) -> bool:
    itag = str(row.get("issue_tag") or "").strip()
    tag = str(issue.get("tag") or issue.get("issue_title") or "").strip()
    if itag and tag and (itag == tag or tag.startswith(itag) or itag.startswith(tag.split()[0])):
        return True
    reason = str(row.get("reason") or "")
    code = re.match(r"(Q\d+)", tag, re.I)
    if code and code.group(1).upper() in reason.upper():
        return True
    label = tag.split(maxsplit=1)[-1] if tag else ""
    return bool(label and len(label) >= 2 and label in reason)


def attach_issue_rewrite_examples(payload: dict[str, Any], original: str) -> None:
    """读报告时为问题附上悬停改写示例（仅改动片段）与原文 rewrite_mark_spans（供本稿原文标红）。"""
    demo = payload.get("rewrite_demo")
    rewrite = ""
    edits: list[dict[str, Any]] = []
    if isinstance(demo, dict):
        rewrite = str(demo.get("rewrite_text") or "").strip()
        edits = [r for r in (demo.get("edit_segments") or []) if isinstance(r, dict)]
    orig = original.strip()
    if not orig:
        return
    second = is_second_pass_report(payload)
    suggestions = payload.get("suggestions") if isinstance(payload.get("suggestions"), list) else []
    sug_idx = 0
    for key in ("issues", "retry_major_issues"):
        block = payload.get(key)
        if not isinstance(block, list):
            continue
        use_rewrite_near_quote = bool(rewrite)
        for issue in block:
            if not isinstance(issue, dict):
                continue
            inferred_ctx = False
            text = solution_example_for_issue(
                orig,
                rewrite,
                issue,
                edits,
                suggestions,
                sug_idx,
                use_rewrite_demo=use_rewrite_near_quote,
            )
            if not text and key == "issues":
                prob = str(issue.get("explanation") or issue.get("issue_title") or "").strip()
                quote = str(issue.get("user_quote") or "").strip()
                label = str(issue.get("issue_title") or issue.get("tag") or "").strip()
                text = _infer_issue_solution_from_context(prob, quote, label, orig)
                inferred_ctx = bool(text)
            if not text and key == "retry_major_issues":
                prob = str(issue.get("explanation") or issue.get("issue_title") or "").strip()
                quote = str(issue.get("user_quote") or "").strip()
                label = str(issue.get("issue_title") or issue.get("tag") or "").strip()
                text = _infer_issue_solution_from_context(prob, quote, label, orig)
                inferred_ctx = bool(text)
            text = _finalize_solution_example(text or "", orig, issue) if text else None
            if text and not inferred_ctx and not _solution_example_relates_to_issue(text, issue, orig):
                text = None
            if text:
                issue["solution_example"] = text
            else:
                issue.pop("solution_example", None)
            if not issue.get("rewrite_mark_spans"):
                from app.services.grading_helpers import _issue_anchor_spans_from_explanation

                anchor_spans = _issue_anchor_spans_from_explanation(orig, issue)
                if anchor_spans:
                    issue["rewrite_mark_spans"] = [
                        {"start": s, "end": e} for s, e in anchor_spans
                    ]
                else:
                    quote = str(issue.get("user_quote") or "").strip()
                    if quote:
                        loc = _locate_quote_span(orig, quote)
                        if loc:
                            issue["rewrite_mark_spans"] = [{"start": loc[0], "end": loc[1]}]
            sug_idx += 1


def validate_rewrite_covers_primary_issues(
    original: str,
    rewrite: str,
    demo: dict[str, Any],
    primary_issues: list[dict[str, Any]],
) -> list[str]:
    if not primary_issues:
        return []
    edits = [r for r in (demo.get("edit_segments") or []) if isinstance(r, dict)]
    errors: list[str] = []
    for issue in primary_issues:
        tag = str(issue.get("tag") or "主要问题").strip()
        if issue_addressed_by_rewrite(original, rewrite, edits, issue):
            continue
        exp = str(issue.get("explanation") or "")[:80]
        hint = str(issue.get("user_quote") or "")[:60]
        msg = f"局部改写未覆盖评分问题「{tag}」"
        if hint:
            msg += f"（须在原文「{hint}…」附近修改）"
        elif exp:
            msg += f"（{exp}）"
        errors.append(msg)
    if len(edits) < len(primary_issues):
        errors.append(
            f"修改片段数（{len(edits)}）少于主要问题数（{len(primary_issues)}），每条问题须有一条局部改写",
        )
    return errors


def validate_rewrite_demo(
    original: str,
    demo: dict[str, Any],
    *,
    strict: bool = False,
    primary_issues: list[dict[str, Any]] | None = None,
) -> tuple[bool, list[str], list[str], dict[str, Any]]:
    """校验改写范例与原文的结构一致性与片段准确性。strict=True 时用于「重新生成」落库门槛。"""
    errors: list[str] = []
    warnings: list[str] = []
    rewrite = str(demo.get("rewrite_text") or "").strip()
    if not rewrite:
        errors.append("改写正文为空")

    orig_norm = _normalize_newlines(original.strip())
    rew_norm = _normalize_newlines(rewrite)
    orig_lines = orig_norm.split("\n")
    rew_lines = rew_norm.split("\n")
    line_match = len(orig_lines) == len(rew_lines)
    if not line_match:
        errors.append(f"换行结构与原文不一致（原文 {len(orig_lines)} 行，改写 {len(rew_lines)} 行）")

    ratio = demo.get("minimal_edit_ratio")
    if ratio is None:
        ratio = round(difflib.SequenceMatcher(None, orig_norm, rew_norm).ratio(), 3)
    if float(ratio) < _MIN_REWRITE_SIMILARITY:
        errors.append(f"改写与原文相似度过低（{ratio}），疑似整篇重写")
    if float(ratio) > 0.995:
        warnings.append("改写与原文几乎相同，修改可能过少")

    keep = [r for r in (demo.get("keep_segments") or []) if isinstance(r, dict)]
    edit = [r for r in (demo.get("edit_segments") or []) if isinstance(r, dict)]
    keep_spans = demo.get("keep_spans") or []
    edit_spans = demo.get("edit_spans") or []

    if len(keep) < _MIN_KEEP_SEGMENTS:
        errors.append(f"标准亮点句不足 {_MIN_KEEP_SEGMENTS} 条")
    if len(edit) < _MIN_EDIT_SEGMENTS:
        errors.append(f"修改片段不足 {_MIN_EDIT_SEGMENTS} 条")
    if not edit_spans:
        errors.append("未能生成可标红的修改区间（edit_spans）")
    if strict and not keep_spans:
        errors.append("未能生成亮点句标绿区间（keep_spans）")

    for row in keep:
        quote = str(row.get("quote") or "").strip()
        if len(quote) < 8:
            errors.append("存在过短的亮点句引用")
            continue
        if orig_norm.find(quote) < 0:
            errors.append("亮点句未在原文中逐字命中")
        if rew_norm.find(quote) < 0:
            errors.append("亮点句须原封不动保留在改写文中")

    max_edit = _max_edit_quote_len(len(rew_norm))
    for row in edit:
        quote = str(row.get("quote") or "").strip()
        if len(quote) < 6:
            errors.append("存在过短的修改片段引用")
            continue
        if len(quote) > max_edit + 4:
            errors.append("单条修改片段过长，不符合局部改写要求")
        if rew_norm.find(quote) < 0:
            errors.append("修改片段未在改写文中逐字命中")

    edit_cov = _highlight_coverage(rew_norm, edit)
    if edit_cov > _MAX_HIGHLIGHT_COVERAGE + 0.03:
        errors.append("修改高亮占比过高，疑似全文标红")

    summary = demo.get("change_summary") or []
    if strict and not (isinstance(summary, list) and any(str(s).strip() for s in summary)):
        warnings.append("缺少改动摘要 change_summary")

    issue_fix_status: list[dict[str, Any]] = []
    if primary_issues:
        issue_fix_status = build_issue_fix_status(orig_norm, rew_norm, demo, primary_issues)
        check_issue_errors = validate_rewrite_covers_primary_issues(
            orig_norm, rew_norm, demo, primary_issues
        )
        if strict:
            errors.extend(check_issue_errors)

    passed = len(errors) == 0
    check = {
        "passed": passed,
        "strict": strict,
        "errors": errors,
        "warnings": warnings,
        "minimal_edit_ratio": ratio,
        "keep_count": len(keep),
        "edit_count": len(edit),
        "line_count_match": line_match,
        "edit_highlight_ratio": round(edit_cov, 3),
        "issue_fix_status": issue_fix_status,
    }
    return passed, errors, warnings, check


async def _call_rewrite_demo_llm(
    db: Session,
    *,
    report: Report,
    cred,
    user_prompt: str,
) -> dict[str, Any]:
    raw, usage = await chat_completion_json(cred, REWRITE_DEMO_SYSTEM, user_prompt)
    log_usage(db, report.user_id, report.grading_job_id, cred, usage, "rewrite_demo")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise AiCallError("UPSTREAM", "改写范例返回非对象 JSON")
    return data


async def generate_rewrite_demo_for_report(
    db: Session,
    *,
    report: Report,
    submission: Submission,
    question: Question | None,
    payload: dict[str, Any],
    require_validation: bool = True,
    save_on_validation_failure: bool = False,
) -> dict[str, Any]:
    content = (submission.content or "").strip()
    if len(content) < 80:
        raise ValueError("ESSAY_TOO_SHORT")

    if payload.get("display_mode") == "reference_only":
        raise ValueError("REFERENCE_ONLY")

    from app.services.grading_helpers import enrich_report_essay_quotes

    payload_for_rewrite = dict(payload)
    enrich_report_essay_quotes(payload_for_rewrite, content)
    primary_issues = collect_primary_issues(payload_for_rewrite, for_rewrite_demo=True)
    if is_second_pass_report(payload_for_rewrite) and not primary_issues:
        raise ValueError("REWRITE_SCOPE_EMPTY")

    ctx = resolve_essay_context(submission, question, db)
    material_excerpt = (ctx.reference_material or "")[:2500]
    second_pass = is_second_pass_report(payload_for_rewrite)
    rewrite_rule = (
        "重作批改：仅针对待继续改进（中等及以上）列表 primary_issues，每条须局部改写；勿处理轻微残留。"
        if second_pass
        else "局部 edit_segments 必须逐条解决 primary_issues，优先在 user_quote 处改写"
    )
    user_input: dict[str, Any] = {
        "essay_prompt": ctx.prompt[:4000],
        "reference_material_excerpt": material_excerpt,
        "student_essay": content[:12000],
        "attempt": int(payload_for_rewrite.get("attempt") or 1),
        "primary_issues": primary_issues,
        "issues": primary_issues,
        "rewrite_rule": rewrite_rule,
        "suggestions": (payload.get("suggestions") or [])[:8],
        "scoring_points": (payload.get("scoring_points") or [])[:8],
        "scoring_rubric": collect_rubric_rows(payload),
        "review_notes": str(payload.get("review_notes") or "")[:800],
    }
    base_prompt = json.dumps(user_input, ensure_ascii=False)

    cred = get_credential(db, report.user_id, CredentialRole.primary)
    if not cred:
        raise AiCallError("NO_CREDENTIAL", "未配置主模型 API Key")

    attempts = _REGENERATE_MAX_ATTEMPTS if require_validation else 1
    last_errors: list[str] = []
    last_demo: dict[str, Any] | None = None
    retry_hint = ""

    for attempt in range(attempts):
        user_prompt = base_prompt
        if retry_hint:
            user_prompt = (
                base_prompt
                + "\n\n"
                + json.dumps(
                    {"validation_retry": True, "fix_requirements": retry_hint},
                    ensure_ascii=False,
                )
            )
        data = await _call_rewrite_demo_llm(db, report=report, cred=cred, user_prompt=user_prompt)
        normalized = _normalize_rewrite_payload(data, content, report_payload=payload)
        if not normalized["rewrite_text"]:
            last_errors = ["改写范例正文为空"]
            retry_hint = "rewrite_text 不得为空；须为局部润色后的完整范文。"
            continue

        demo: dict[str, Any] = {
            "status": "ready",
            "schema_version": REWRITE_DEMO_SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "regenerate_attempt": attempt + 1,
            **normalized,
        }
        passed, errors, warnings, check = validate_rewrite_demo(
            content,
            demo,
            strict=require_validation,
            primary_issues=primary_issues,
        )
        if warnings:
            check["warnings"] = list(check.get("warnings") or []) + warnings
        demo["validation_check"] = check
        last_demo = demo

        if passed:
            return demo

        if not require_validation:
            demo["minimal_edit_warning"] = (
                (demo.get("minimal_edit_warning") or "")
                + (" " if demo.get("minimal_edit_warning") else "")
                + "；".join(errors)
            ).strip()
            return demo

        last_errors = errors
        must_rewrite: list[dict[str, str]] = []
        rew = normalized.get("rewrite_text") or ""
        for issue in primary_issues:
            quote = str(issue.get("user_quote") or "").strip()
            span = _locate_quote_span(content, quote) if quote else None
            if not span:
                continue
            anchor = content[span[0] : span[1]]
            if anchor in rew:
                must_rewrite.append(
                    {
                        "issue_tag": str(issue.get("tag") or ""),
                        "source_quote": anchor[:200],
                        "explanation": str(issue.get("explanation") or "")[:200],
                    }
                )
        retry_hint = json.dumps(
            {
                "validation_errors": errors[:8],
                "must_rewrite_quotes": must_rewrite,
                "instruction": "上述 source_quote 在 rewrite_text 中仍原文出现，必须在对应位置改写并写入 edit_segments（含 issue_tag/source_quote）",
            },
            ensure_ascii=False,
        )

    if save_on_validation_failure and last_demo:
        check = last_demo.get("validation_check")
        if not isinstance(check, dict):
            check = {}
        check["passed"] = False
        check["errors"] = list(check.get("errors") or last_errors)[:12]
        last_demo["validation_check"] = check
        note = str(last_demo.get("minimal_edit_warning") or "").strip()
        extra = "；".join(last_errors[:4])
        if extra:
            last_demo["minimal_edit_warning"] = (note + " " + extra).strip() if note else extra
        return last_demo

    raise ValueError("REWRITE_VALIDATION_FAILED:" + "；".join(last_errors[:8]))
