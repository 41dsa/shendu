"""根据题干与材料生成带采分点标注的参考范文（AI，仅供参考）。"""

from __future__ import annotations

import difflib
import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.essay import essay_length_ratio, official_essay_char_count
from app.domain.scoring_engine.input_gate import run_input_gate
from app.domain.scoring_engine.types import ScoringEngineResult
from app.models.entities import CredentialRole, Question, Report, Submission
from app.services.ai_client import AiCallError, chat_completion_json, get_credential
from app.services.essay_context import EssayGradingContext, resolve_essay_context, word_bounds_for_context
from app.services.grading_service import log_usage, rule_score_fallback
from app.services.scoring_engine.orchestrator import run_scoring_engine_online
from app.services.rewrite_demo_service import MARKDOWN_BODY_INDENT, collect_rubric_rows

REFERENCE_SAMPLE_SCHEMA_VERSION = 6
REFERENCE_SAMPLE_MAX_ATTEMPTS = 6
REFERENCE_SAMPLE_MIN_MARKS = 4
REFERENCE_SAMPLE_REJECT_DETAIL = (
    "参考范例未通过评分引擎分数档位（二类中上）抽检，不再提供低分模版"
)

REFERENCE_SAMPLE_SYSTEM = """你是申论大作文写作教练。根据题目要求与给定材料，写一篇「参考范文」（不是替考生交卷，仅供学习）。
硬性要求：
1. 整体水平对应「二类中上」（约 28/40 分档起，随满分缩放；勿写成一类文口吻）。
2. sample_text 结构：① 第一行仅为文章标题（自拟题目，无段首缩进，不是分论点）；② 可选一段引论（有缩进）；③ 恰好 3 或 4 个分论点段，每段只论证一个分论点，段首「　　」后第一句即段旨判断句；④ 可选一段结论。禁止把多个分论点写在同一段；禁止把「分论点1/2」、提纲、作答要求原文（如「要求：」）写进正文。分论点段之间必须空一行。正文字数须达到 user_input 中 word_min～word_max 的建议区间（至少不低于 word_min 的 85%），并充分扣材料与 focus_points。
3. body_theses：恰好 3 或 4 条，每条对应且仅对应一个分论点段（不含标题、引论、结论）。index 从 1 连续；title（15～36 字）须从该段首句提炼，核心表述须出现在该段首句中（不得出现在文章标题行）。
4. mark_segments：6～12 条采分点标注（不是分论点！是段内扣材料、分析、过渡、对策等写法示范）。每条 quote 为 sample_text 连续子串（12～80 字）；必填 point_label（采分类型，如「立意扣题」「材料运用」）、thesis_index（1～4，标明属于 body_theses 中第几个分论点段）、why（30～120 字写法解析）。禁止在 mark_segments 里再写独立分论点标题。
5. target_tier_note：一句话说明模拟档位。
6. 不得照抄材料整段；不得出现「作为 AI」等元话语。
仅输出 JSON：
{
  "sample_text": string,
  "target_tier_note": string,
  "body_theses": [{"index": number, "title": string}],
  "mark_segments": [{"quote": string, "point_label": string, "thesis_index": number, "why": string}]
}"""


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _format_reference_sample_text(text: str) -> str:
    """参考范文独立排版：首行标题不缩进，正文段首全角缩进；不镜像题干行结构。"""
    lines = _normalize_newlines(text).strip().split("\n")
    out: list[str] = []
    seen_body = False
    for line in lines:
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        stripped = line.lstrip("\u3000 ").lstrip()
        if not seen_body:
            out.append(stripped)
            seen_body = True
            continue
        if line.startswith("\u3000") or line.startswith("　"):
            out.append(line)
        else:
            out.append(MARKDOWN_BODY_INDENT + stripped)
    return _ensure_reference_paragraph_gaps("\n".join(out))


def _ensure_reference_paragraph_gaps(text: str) -> str:
    """段首缩进行前补空行，便于模板阅读分论点。"""
    lines = text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    body_started = False
    for line in lines:
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            continue
        para = line.startswith("\u3000") or line.startswith("　")
        if para and body_started and out and out[-1] != "":
            out.append("")
        if para:
            body_started = True
        out.append(line)
    return "\n".join(out)


def _scrub_prompt_leak(text: str) -> str:
    lines = _normalize_newlines(text).split("\n")
    out: list[str] = []
    for line in lines:
        if re.search(r"要求\s*[：:]", line):
            cleaned = re.sub(r"要求\s*[：:][^\n]*", "", line).strip()
            if cleaned:
                out.append(cleaned)
            continue
        out.append(line)
    return "\n".join(out)


def _sentences_from_paragraph(line: str) -> list[str]:
    body = line.lstrip("\u3000 ").lstrip()
    if not body:
        return []
    parts = re.split(r"(?<=[。！？；])", body)
    return [p.strip() for p in parts if p.strip()]


def _split_long_body_paragraphs(text: str, thesis_count: int) -> str:
    """将过长单段拆成多段，便于分论点一一对应。"""
    sample = _normalize_newlines(text)
    for _ in range(6):
        body = _body_paragraphs_after_title(sample)
        if len(body) >= thesis_count:
            return _ensure_reference_paragraph_gaps(sample)
        pos, line = max(body, key=lambda item: len(item[1]))
        sents = _sentences_from_paragraph(line)
        if len(sents) < 2 or len(line) < 100:
            return _ensure_reference_paragraph_gaps(sample)
        chunks: list[str] = []
        for idx, sent in enumerate(sents):
            chunks.append(MARKDOWN_BODY_INDENT + sent)
            if idx < len(sents) - 1:
                chunks.append("")
        lines = sample.split("\n")
        cursor = 0
        replaced = False
        for li, ln in enumerate(lines):
            if cursor == pos and ln == line:
                lines[li : li + 1] = chunks
                replaced = True
                break
            cursor += len(ln) + 1
        if not replaced:
            return _ensure_reference_paragraph_gaps(sample)
        sample = "\n".join(lines)
    return _ensure_reference_paragraph_gaps(sample)


def _lead_sentence_plain(line: str) -> str:
    body = line.lstrip("\u3000 ").lstrip()
    for sep in ("。", "！", "？", "；"):
        idx = body.find(sep)
        if idx >= 0:
            return body[: idx + 1]
    return body[:40]


def _sync_body_theses_from_sample(sample: str, theses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(theses, key=lambda t: int(t["index"]))
    body = _body_paragraphs_after_title(sample)
    slice_paras = _slice_thesis_paragraphs(body, len(ordered))
    if not slice_paras or len(slice_paras) < len(ordered):
        return theses
    synced: list[dict[str, Any]] = []
    for t, (_, line) in zip(ordered, slice_paras[: len(ordered)], strict=False):
        lead = _lead_sentence_plain(line).strip("。！？；")
        title = lead if len(lead) >= 6 else str(t.get("title") or "")
        synced.append({"index": int(t["index"]), "title": title[:80]})
    return synced


def _resolve_quote_in_text(text: str, quote: str, *, min_len: int = 8) -> str | None:
    q = quote.strip()
    if len(q) < min_len:
        return None
    if q in text:
        return q
    compact_text = text.replace(" ", "").replace("\n", "")
    compact_q = q.replace(" ", "")
    if len(compact_q) >= min_len and compact_q in compact_text:
        start = compact_text.find(compact_q)
        return compact_text[start : start + len(compact_q)]
    n = len(q)
    best_ratio = 0.0
    best_slice = ""
    step = max(1, n // 5)
    for i in range(0, max(1, len(text) - n + 1), step):
        window = text[i : i + n]
        if len(window) < min_len:
            continue
        ratio = difflib.SequenceMatcher(None, q, window).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_slice = window
            if ratio >= 0.92:
                break
    if best_ratio >= 0.88 and len(best_slice) >= min_len:
        return best_slice
    return None


def _autofill_mark_segments(
    text: str,
    theses: list[dict[str, Any]],
    existing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if len(existing) >= REFERENCE_SAMPLE_MIN_MARKS:
        return existing
    out = list(existing)
    seen = {str(r.get("quote") or "") for r in out}
    body = _body_paragraphs_after_title(text)
    slice_paras = _slice_thesis_paragraphs(body, len(theses)) or []
    for t, para in zip(sorted(theses, key=lambda x: int(x["index"])), slice_paras, strict=False):
        if len(out) >= REFERENCE_SAMPLE_MIN_MARKS:
            break
        ti = int(t["index"])
        line = para[1]
        candidates = [_lead_sentence_plain(line)]
        candidates.extend(_sentences_from_paragraph(line)[1:3])
        for cand in candidates:
            quote = cand.strip()
            if len(quote) < 8:
                continue
            resolved = _resolve_quote_in_text(text, quote, min_len=8)
            if not resolved or resolved in seen:
                continue
            seen.add(resolved)
            out.append(
                {
                    "quote": resolved,
                    "point_label": "写法示范",
                    "thesis_index": ti,
                    "why": "段内扣题与论证示范",
                }
            )
            if len(out) >= REFERENCE_SAMPLE_MIN_MARKS:
                break
    return out


def _repair_reference_sample_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    sample = _scrub_prompt_leak(str(payload.get("sample_text") or "").strip())
    sample = _format_reference_sample_text(sample)
    theses = _validate_body_theses(payload.get("body_theses"))
    if theses:
        sample = _split_long_body_paragraphs(sample, len(theses))
        theses = _sync_body_theses_from_sample(sample, theses)
    payload["sample_text"] = sample
    if theses:
        payload["body_theses"] = theses
    raw_marks = payload.get("mark_segments")
    if isinstance(raw_marks, list) and theses:
        repaired: list[dict[str, Any]] = []
        for row in raw_marks:
            if not isinstance(row, dict):
                continue
            quote = str(row.get("quote") or "").strip()
            resolved = _resolve_quote_in_text(sample, quote) if quote else None
            if not resolved:
                continue
            repaired.append({**row, "quote": resolved})
        payload["mark_segments"] = _autofill_mark_segments(sample, theses, repaired)
    return payload


def _title_present_in_text(title: str, text: str) -> bool:
    t = title.strip()
    if not t or not text:
        return False
    if t in text:
        return True
    compact = t.replace(" ", "").replace("　", "")
    blob = text.replace(" ", "").replace("　", "")
    if len(compact) >= 8 and compact in blob:
        return True
    for length in range(min(len(t), 28), 7, -1):
        for i in range(len(t) - length + 1):
            frag = t[i : i + length]
            if frag in text:
                return True
    return False


def _body_paragraphs_after_title(text: str) -> list[tuple[int, str]]:
    title_end = _essay_title_line_end(text)
    return [(pos, line) for pos, line in _body_paragraph_line_starts(text) if pos >= title_end]


def _slice_thesis_paragraphs(body: list[tuple[int, str]], thesis_count: int) -> list[tuple[int, str]] | None:
    m = len(body)
    n = thesis_count
    if m < n:
        return None
    if m == n:
        return body
    if m == n + 1:
        return body[1:]
    if m >= n + 2:
        return body[1 : 1 + n]
    return body[-n:]


def _body_paragraph_line_starts(text: str) -> list[tuple[int, str]]:
    lines = text.replace("\r\n", "\n").split("\n")
    cursor = 0
    out: list[tuple[int, str]] = []
    for line in lines:
        if line.strip() and (line.startswith("\u3000") or line.startswith("　")):
            out.append((cursor, line))
        cursor += len(line) + 1
    return out


def _line_content_start(line: str, global_start: int) -> int:
    stripped = line.lstrip("\u3000 ").lstrip()
    return global_start + (len(line) - len(stripped))


def _opening_sentence_span(line: str, global_start: int) -> tuple[int, int]:
    content_start = _line_content_start(line, global_start)
    body = line.lstrip("\u3000 ").lstrip()
    if not body:
        return content_start, content_start
    for sep in ("。", "！", "？", "；"):
        idx = body.find(sep)
        if idx >= 0:
            return content_start, content_start + idx + 1
    return content_start, global_start + len(line)


def _essay_title_line_end(text: str) -> int:
    """首行（文章标题）字符区间上界，分论点不得锚定在标题行。"""
    lines = text.replace("\r\n", "\n").split("\n")
    cursor = 0
    for line in lines:
        if line.strip():
            if line.startswith("\u3000") or line.startswith("　"):
                return cursor
            return cursor + len(line)
        cursor += len(line) + 1
    return 0


def _compute_thesis_anchors(text: str, theses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """分论点段首句在正文中的位置（不含标题行）。"""
    ordered = sorted(theses, key=lambda t: int(t["index"]))
    body = _body_paragraphs_after_title(text)
    slice_paras = _slice_thesis_paragraphs(body, len(ordered))
    if not slice_paras:
        return []

    used: set[int] = set()
    assigned: list[tuple[dict[str, Any], tuple[int, str]]] = []

    for ti, t in enumerate(ordered):
        title = str(t["title"])
        hit: tuple[int, str] | None = None
        for pi, para in enumerate(slice_paras):
            if pi in used:
                continue
            if _title_present_in_text(title, para[1]):
                hit = para
                used.add(pi)
                break
        if hit is None and ti < len(slice_paras):
            for pi in range(len(slice_paras)):
                if pi not in used:
                    hit = slice_paras[pi]
                    used.add(pi)
                    break
        if hit is None:
            continue
        assigned.append((t, hit))

    anchors: list[dict[str, Any]] = []
    for t, (pos, line) in assigned:
        lead_start, lead_end = _opening_sentence_span(line, pos)
        anchors.append(
            {
                "thesis_index": int(t["index"]),
                "title": str(t["title"]),
                "start": pos,
                "lead_start": lead_start,
                "lead_end": lead_end,
            }
        )
    return sorted(anchors, key=lambda a: a["start"])


def _assert_thesis_paragraph_structure(text: str, theses: list[dict[str, Any]]) -> None:
    if "要求：" in text or "要求:" in text:
        raise ValueError("PROMPT_LEAK_IN_SAMPLE")
    anchors = _compute_thesis_anchors(text, theses)
    if len(anchors) != len(theses):
        raise ValueError("THESIS_PARAGRAPH_MISMATCH")
    anchor_by_idx = {int(a["thesis_index"]): a for a in anchors}
    for t in theses:
        title = str(t.get("title") or "")
        idx = int(t.get("index") or 0)
        anchor = anchor_by_idx.get(idx)
        if anchor is None:
            raise ValueError("THESES_NOT_IN_TEXT")
        start = int(anchor["start"])
        para_line = text[start : text.find("\n", start)] if start < len(text) else ""
        if not _title_present_in_text(title, para_line or text):
            raise ValueError("THESES_NOT_IN_TEXT")
    title_end = _essay_title_line_end(text)
    first_line = text.replace("\r\n", "\n").split("\n")[0] if text else ""
    if first_line.strip() and _title_present_in_text(str(theses[0].get("title") or ""), first_line):
        raise ValueError("THESIS_ON_TITLE")


def target_sample_score_band(max_score: float) -> tuple[float, float]:
    """二类中上抽检下沿（约 28/40，随满分缩放）。"""
    scale = max_score / 40.0 if max_score > 0 else 1.0
    return round(28 * scale, 1), round(34 * scale, 1)


def conservative_merged_total_floor(engine_total: float, max_score: float) -> float:
    """抄交后融合总分的可能下界（与 merge_engine_with_llm_payload 保守情形对齐）。"""
    max_delta = float(settings.layered_scoring_max_llm_delta)
    llm_low = max(0.0, engine_total - max_delta)
    blended = round(engine_total * 0.75 + llm_low * 0.25, 1)
    return min(engine_total, blended)


async def verify_reference_sample_grading_score(
    db: Session,
    *,
    ctx: EssayGradingContext,
    content: str,
    report: Report,
    submission: Submission,
    min_total: float,
    max_score: float,
) -> tuple[bool, dict[str, Any]]:
    """用与正式批改相同的引擎路径抽检范文，确保抄交可达目标档位下沿。"""
    gate = run_input_gate(ctx, content)
    word_min, word_max = word_bounds_for_context(ctx)
    chars = official_essay_char_count(content)
    word_ratio = essay_length_ratio(chars, word_min)
    meta: dict[str, Any] = {
        "min_total": min_total,
        "word_min": word_min,
        "word_max": word_max,
        "essay_chars": chars,
        "word_ratio": round(word_ratio, 3),
    }
    if not gate.passed:
        meta["reason"] = gate.reason or "gate_reject"
        return False, meta

    engine_total: float
    tier_id: str | None = None
    if settings.layered_scoring_engine_enabled:
        job_id = report.grading_job_id or report.id
        out = await run_scoring_engine_online(
            db,
            ctx,
            content,
            user_id=report.user_id,
            job_id=job_id,
            submission_id=submission.id,
            persist_hit_logs=False,
        )
        if isinstance(out, dict):
            meta["reason"] = out.get("short_circuit_reason") or "gate_reject"
            return False, meta
        assert isinstance(out, ScoringEngineResult)
        engine_total = float(out.total_score)
        tier_id = out.tier.tier_id
    else:
        engine_total = float(rule_score_fallback(ctx, content))

    floor_total = conservative_merged_total_floor(engine_total, max_score)
    meta.update(
        {
            "engine_total": round(engine_total, 1),
            "merged_floor": round(floor_total, 1),
            "tier_id": tier_id,
        }
    )
    if floor_total + 1e-6 < min_total:
        meta["reason"] = "below_target_band"
        return False, meta
    return True, meta


def _validate_body_theses(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        try:
            idx = int(row.get("index"))
        except (TypeError, ValueError):
            continue
        if idx < 1 or idx > 4 or idx in seen:
            continue
        title = str(row.get("title") or row.get("sub_thesis") or "").strip()[:80]
        if len(title) < 6:
            continue
        seen.add(idx)
        out.append({"index": idx, "title": title})
    out.sort(key=lambda r: r["index"])
    if len(out) < 3 or len(out) > 4:
        return []
    return out


def _validate_mark_segments(
    text: str,
    raw: Any,
    *,
    body_theses: list[dict[str, Any]],
    max_items: int = 12,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    valid_indexes = {int(t["index"]) for t in body_theses}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in raw:
        if not isinstance(row, dict):
            continue
        quote = str(row.get("quote") or "").strip()
        label = str(row.get("point_label") or row.get("label") or "").strip()[:48]
        why = str(row.get("why") or row.get("reason") or "").strip()[:240]
        try:
            thesis_index = int(row.get("thesis_index") or row.get("thesis_idx") or 0)
        except (TypeError, ValueError):
            thesis_index = 0
        if thesis_index not in valid_indexes:
            continue
        resolved = _resolve_quote_in_text(text, quote, min_len=8)
        if not resolved:
            continue
        quote = resolved
        if quote in seen:
            continue
        seen.add(quote)
        out.append(
            {
                "quote": quote,
                "point_label": label or "采分点",
                "thesis_index": thesis_index,
                "why": why or "写法示范",
            }
        )
        if len(out) >= max_items:
            break
    out.sort(key=lambda r: text.find(str(r["quote"])))
    return out


def _segments_to_spans(text: str, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for idx, row in enumerate(segments):
        quote = str(row.get("quote") or "")
        pos = text.find(quote)
        if pos < 0:
            continue
        spans.append(
            {
                "start": pos,
                "end": pos + len(quote),
                "point_label": row.get("point_label"),
                "thesis_index": row.get("thesis_index"),
                "why": row.get("why"),
                "segment_index": idx + 1,
            }
        )
    return spans


def _normalize_reference_sample(
    data: dict[str, Any],
    *,
    prompt: str,
    max_score: float,
) -> dict[str, Any]:
    data = _repair_reference_sample_payload(data)
    sample = str(data.get("sample_text") or "").strip()
    if not sample:
        raise ValueError("EMPTY_SAMPLE")
    theses = _validate_body_theses(data.get("body_theses"))
    if not theses:
        raise ValueError("NO_THESES")
    _assert_thesis_paragraph_structure(sample, theses)
    raw_marks = data.get("mark_segments")
    marks = _validate_mark_segments(
        sample,
        raw_marks if isinstance(raw_marks, list) else [],
        body_theses=theses,
    )
    if len(marks) < REFERENCE_SAMPLE_MIN_MARKS:
        marks = _validate_mark_segments(
            sample,
            _autofill_mark_segments(sample, theses, marks),
            body_theses=theses,
        )
    anchors = _compute_thesis_anchors(sample, theses)
    lo, hi = target_sample_score_band(max_score)
    note = str(data.get("target_tier_note") or "").strip()
    if not note:
        note = f"参考档位：二类中上（引擎抽检不低于约 {lo:g}/{max_score:g} 分）"
    return {
        "sample_text": sample,
        "target_tier_note": note,
        "target_score_band": [lo, hi],
        "body_theses": theses,
        "thesis_anchors": anchors,
        "mark_segments": marks,
        "mark_spans": _segments_to_spans(sample, marks),
    }


async def generate_reference_sample_for_report(
    db: Session,
    *,
    report: Report,
    submission: Submission,
    question: Question | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("display_mode") == "reference_only":
        raise ValueError("REFERENCE_ONLY")

    ctx = resolve_essay_context(submission, question, db)
    prompt = (ctx.prompt or "").strip()
    material = (ctx.reference_material or "").strip()
    if len(prompt) < 20:
        raise ValueError("PROMPT_TOO_SHORT")

    try:
        max_score = float(payload.get("display_max_score") or payload.get("max_score") or ctx.score or 40)
    except (TypeError, ValueError):
        max_score = 40.0
    lo, hi = target_sample_score_band(max_score)
    word_min, word_max = word_bounds_for_context(ctx)
    rubric = collect_rubric_rows(payload)

    user_input = {
        "essay_prompt": prompt[:4000],
        "reference_material": material[:8000],
        "max_score": max_score,
        "word_min": word_min,
        "word_max": word_max,
        "target_score_band": [lo, hi],
        "target_quality": (
            f"二类中上（引擎抽检总分须≥{lo:g}）；"
            "正文 3～4 个分论点段，采分标注挂在对应分论点下"
        ),
        "scoring_rubric": rubric[:12],
        "focus_points": (ctx.focus_points or [])[:8],
        "student_attempt_note": "范文与考生原文无关；须达到可抄交仍达目标档位的质量",
    }

    cred = get_credential(db, report.user_id, CredentialRole.primary)
    if not cred:
        raise AiCallError("NO_CREDENTIAL", "未配置主模型 API Key")

    last_error: ValueError | None = None
    repair_hint = ""
    for attempt in range(REFERENCE_SAMPLE_MAX_ATTEMPTS):
        user_payload = dict(user_input)
        if repair_hint:
            user_payload["repair_hint"] = repair_hint
        raw, usage = await chat_completion_json(
            cred,
            REFERENCE_SAMPLE_SYSTEM,
            json.dumps(user_payload, ensure_ascii=False),
        )
        log_usage(db, report.user_id, report.grading_job_id, cred, usage, "reference_sample")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise AiCallError("UPSTREAM", "参考范文返回非对象 JSON")
        try:
            normalized = _normalize_reference_sample(data, prompt=prompt, max_score=max_score)
            marks = normalized["mark_segments"]
            if len(marks) < REFERENCE_SAMPLE_MIN_MARKS:
                raise ValueError("NO_MARKS")
            score_ok, score_meta = await verify_reference_sample_grading_score(
                db,
                ctx=ctx,
                content=str(normalized["sample_text"]),
                report=report,
                submission=submission,
                min_total=lo,
                max_score=max_score,
            )
            if not score_ok:
                raise ValueError(f"SAMPLE_SCORE_TOO_LOW:{json.dumps(score_meta, ensure_ascii=False)}")
            normalized["score_verification"] = score_meta
            break
        except ValueError as exc:
            last_error = exc
            code = str(exc)
            if code.startswith("SAMPLE_SCORE_TOO_LOW:"):
                repair_hint = (
                    "上次范文在评分引擎抽检中未达二类中上档位目标。请加长并加厚："
                    "扣材料事例、对策与思辨；字数达到 word_min 以上；"
                    "保持 3～4 分论点分段与段旨首句。"
                    f" 引擎反馈：{code.split(':', 1)[-1]}"
                )
            else:
                repair_hint = (
                    f"上次输出未通过校验（{code}）。请严格重写：第一行仅自拟标题；"
                    "3～4 个分论点各占独立一段（段首「　　」+ 段旨首句）；"
                    "禁止写入「要求：」或题干原文；body_theses.title 须能在对应段首句中找到。"
                )
            if attempt + 1 >= REFERENCE_SAMPLE_MAX_ATTEMPTS:
                raise last_error from exc
    else:
        if last_error:
            raise last_error
        raise ValueError("EMPTY_SAMPLE")

    return {
        "status": "ready",
        "schema_version": REFERENCE_SAMPLE_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        **normalized,
    }


def refresh_reference_sample_display(block: dict[str, Any]) -> bool:
    if not isinstance(block, dict) or block.get("status") != "ready":
        return False
    text = _format_reference_sample_text(str(block.get("sample_text") or "").strip())
    if not text:
        return False
    block["sample_text"] = text
    theses = _validate_body_theses(block.get("body_theses"))
    if theses:
        block["body_theses"] = theses
    marks = block.get("mark_segments")
    if not isinstance(marks, list):
        marks = []
    rows = [r for r in marks if isinstance(r, dict)]
    if theses:
        block["mark_segments"] = _validate_mark_segments(text, rows, body_theses=theses)
        block["thesis_anchors"] = _compute_thesis_anchors(text, theses)
    else:
        block["mark_segments"] = []
        block.pop("thesis_anchors", None)
    block["mark_spans"] = _segments_to_spans(text, block.get("mark_segments") or [])
    return True
