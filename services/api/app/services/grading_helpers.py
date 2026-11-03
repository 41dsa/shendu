import hashlib
import json
import re
from typing import Any

from app.domain.essay import issue_tag_from_core_problem, resolve_issue_badge


def normalize_answer(text: str) -> str:
    t = re.sub(r"\s+", "", text.strip())
    return t.lower()


def answer_hash(question_id: str, content: str, rubric_version: str = "v1") -> str:
    raw = f"{question_id}:{rubric_version}:{normalize_answer(content)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_confidence(
    total_score: float,
    rule_score: float,
    max_score: float,
    consensus_delta: float | None,
    word_ratio: float,
    *,
    consensus_discarded: bool = False,
) -> str:
    """
    总分数置信度（非整份批改可信度）。完整维度/问题/建议来自主评，不因本字段降级。
    「low」仅保留给字数严重不足等硬条件，避免用户误以为 AI 批改无效。
    """
    if word_ratio < 0.3:
        return "low"
    rule_gap = abs(total_score - rule_score)
    rule_medium = max(3.0, max_score * 0.12)
    rule_high = max(1.5, max_score * 0.06)

    if consensus_discarded:
        return "medium"

    if consensus_delta is not None and consensus_delta > 1.5:
        return "medium"
    if rule_gap > rule_medium:
        return "medium"
    if consensus_delta is not None and consensus_delta > 0.8:
        return "medium"
    if rule_gap > rule_high:
        return "medium"
    # 双路总分一致时提高总分数置信度（完整批改 + 复核均通过）
    if consensus_delta is not None and consensus_delta <= 1.0:
        return "high"
    return "medium" if rule_gap > rule_high else "high"


def confidence_user_note(
    confidence: str,
    word_ratio: float,
    *,
    consensus_ran: bool = False,
    consensus_discarded: bool = False,
) -> str:
    if confidence == "low":
        return "作文字数明显不足，总分仅供参考；仍可根据维度与建议改进写法。"
    if consensus_ran and not consensus_discarded and confidence == "high":
        return "已完成完整批改与双路总分复核且结果接近；总分与维度、建议均可作为主要参考。"
    if consensus_discarded:
        return "已完成双路检验，但两次总分差距较大，报告采用完整批改主评；维度与建议仍可直接用于修改。"
    if consensus_ran:
        return "已完成双路总分检验；各维度得分与问题、建议可直接用于修改，总分请结合合理区间理解。"
    if confidence == "medium":
        return "总分建议在合理区间内理解；各维度得分与问题、建议可直接用于修改。"
    return "总分与维度反馈均可作为主要参考。"


def compute_consensus_rate(scores: list[float], max_score: float) -> float:
    if len(scores) < 2 or max_score <= 0:
        return 100.0
    mean = sum(scores) / len(scores)
    var = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = var**0.5
    rate = max(0.0, min(100.0, (1 - std / max_score) * 100))
    return round(rate, 1)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _infer_hit(earned: float, max_score: float) -> str:
    if max_score <= 0:
        return "miss"
    ratio = earned / max_score
    if ratio >= 0.85:
        return "full"
    if ratio >= 0.5:
        return "partial"
    return "miss"


def sync_scoring_points_hit_from_earned(payload: dict[str, Any]) -> None:
    """维度 hit 与 earned/max 一致，避免校准总分后仍显示 LLM 的「未命中」。"""
    points = payload.get("scoring_points")
    if not isinstance(points, list):
        return
    for row in points:
        if not isinstance(row, dict):
            continue
        mx = _point_max_value(row, 0.0)
        if mx <= 0:
            continue
        earned = _point_earned_value(row)
        row["hit"] = _infer_hit(earned, mx)


def _parse_score_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"([\d]+(?:\.\d+)?)", value.replace(" ", ""))
        if m:
            return float(m.group(1))
    return _to_float(value, default=-1.0) if value is not None else None


def _payload_section(payload: dict[str, Any], *logical_names: str) -> Any:
    """按逻辑名取块：支持 `综合评分` 与 `1_综合评分` 等带序号前缀的键。"""
    for name in logical_names:
        if name in payload:
            return payload[name]
    for key, val in payload.items():
        if not isinstance(key, str):
            continue
        for name in logical_names:
            if key == name or key.endswith(f"_{name}") or name in key:
                return val
    return None


def _dimension_rows(section: Any) -> list[dict[str, Any]]:
    if isinstance(section, list):
        return [r for r in section if isinstance(r, dict)]
    if isinstance(section, dict):
        for key in ("维度", "dimensions", "items", "分项", "scoring_points"):
            block = section.get(key)
            if isinstance(block, list):
                return [r for r in block if isinstance(r, dict)]
    return []


def _issue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    core = _payload_section(payload, "核心问题", "problems")
    if isinstance(core, list):
        return [r for r in core if isinstance(r, dict)]
    return []


_SUMMARY_REVIEW_KEYS = (
    "总体说明",
    "总体得分原因",
    "总体原因",
    "总体评价",
    "总体评述",
)


def _summary_review_text(summary: dict[str, Any]) -> str:
    for key in _SUMMARY_REVIEW_KEYS:
        val = summary.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _looks_like_engine_tier_excerpt(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    return bool(re.match(r"^[一二三四]类文[（(]", t))


def flag_review_tier_mismatch(payload: dict[str, Any], *, max_score: float) -> None:
    """总分与总评中的「一类/二类」表述严重不符时打标（便于排查，不删改主评原文）。"""
    try:
        total = float(payload.get("total_score") or 0)
    except (TypeError, ValueError):
        return
    if max_score <= 0 or total <= 0:
        return
    notes = str(payload.get("review_notes") or "")
    if not notes:
        return
    ratio = total / max_score
    high_tier = bool(re.search(r"(?:一类|二类)(?:文|卷|档|中)?", notes))
    if ratio <= 0.22 and high_tier and not re.search(r"(?:三类|四类)", notes):
        payload["review_tier_score_mismatch"] = True


def resolve_review_notes_excerpt(payload: dict[str, Any]) -> None:
    """阅卷总评摘录：优先 LLM 综合评语文本；档次区间由 refresh_score_display_context 按作答要求满分统一。"""
    summary = _payload_section(payload, "综合评分")
    from_summary = _summary_review_text(summary) if isinstance(summary, dict) else ""
    existing = str(payload.get("review_notes") or "").strip()
    tier_note = str(payload.get("tier_label") or payload.get("engine_tier_note") or "").strip()

    if from_summary:
        if not existing or existing == tier_note or _looks_like_engine_tier_excerpt(existing):
            payload["review_notes"] = from_summary
        return
    if existing and not _looks_like_engine_tier_excerpt(existing):
        return
    if _looks_like_engine_tier_excerpt(existing):
        payload["review_notes"] = ""


def display_total_score(payload: dict[str, Any]) -> float:
    """报告展示用总分（兼容中文键与 total_score=0 的脏数据）。"""
    normalized = normalize_llm_report_payload(dict(payload))
    return float(normalized.get("total_score") or 0)


def resolved_primary_llm_score(payload: dict[str, Any]) -> float:
    """与「报告采用」一致的主评展示分（避免综合评分 JSON 与合并总分两套数）。"""
    total = float(payload.get("total_score") or 0)
    if total <= 0:
        total = display_total_score(payload)
    for key in ("primary_llm_score", "llm_score"):
        try:
            val = float(payload.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if val > 0 and (total <= 0 or abs(val - total) <= 2.0):
            return val
    if total > 0:
        return total
    summary = _payload_section(payload, "综合评分")
    if isinstance(summary, dict):
        parsed = _parse_score_value(summary.get("总分"))
        if parsed is not None and parsed > 0:
            return parsed
    return 0.0


def _infer_hit_from_earned(earned: float, max_score: float) -> str:
    return _infer_hit(earned, max_score)


_HOLISTIC_DIMENSION_LABELS = frozenset({"总分", "综合评分", "综合得分", "卷面总分", "总分得分"})


def _essay_max_from_payload(payload: dict[str, Any], default: float = 40.0) -> float:
    try:
        return float(payload.get("max_score") or default)
    except (TypeError, ValueError):
        return default


def is_holistic_dimension_row(label: str, max_score: float, *, essay_max: float) -> bool:
    """模型有时把卷面总分写进「分项评分」一行（label=总分、满分=40），会与顶部报告总分重复且不一致。"""
    lab = (label or "").strip()
    if not lab:
        return False
    if lab in _HOLISTIC_DIMENSION_LABELS:
        return True
    if lab.startswith("总分") and max_score >= essay_max * 0.85:
        return True
    if lab in ("综合", "整体评价") and max_score >= essay_max * 0.85:
        return True
    return False


def strip_holistic_dimension_rows(payload: dict[str, Any]) -> None:
    points = payload.get("scoring_points")
    if not isinstance(points, list) or not points:
        return
    essay_max = _essay_max_from_payload(payload)
    kept: list[dict[str, Any]] = []
    stripped = 0
    for row in points:
        if not isinstance(row, dict):
            kept.append(row)
            continue
        label = str(row.get("label") or "")
        mx = _to_float(row.get("max") or row.get("max_score"), 0.0)
        if is_holistic_dimension_row(label, mx, essay_max=essay_max):
            stripped += 1
            reason = str(row.get("reason") or row.get("说明") or "").strip()
            if reason:
                existing = str(payload.get("review_notes") or "").strip()
                if not existing:
                    payload["review_notes"] = reason
                elif reason not in existing:
                    payload["review_notes"] = f"{existing} {reason}".strip()
            continue
        kept.append(row)
    if stripped:
        payload["scoring_points"] = kept
        payload["holistic_dimension_stripped"] = True


def _point_earned_value(row: dict[str, Any]) -> float:
    for key in ("earned", "score", "得分"):
        if row.get(key) is not None:
            return _to_float(row.get(key))
    return 0.0


def _point_max_value(row: dict[str, Any], default: float = 0.0) -> float:
    for key in ("max", "max_score", "满分"):
        if row.get(key) is not None:
            return _to_float(row.get(key), default)
    return default


def dimension_earned_totals(payload: dict[str, Any]) -> tuple[float, float]:
    """各评分维度 earned / max 加总；scoring_points 为 0 时回退 dimension_scores、分项评分。"""
    dim_sum = 0.0
    dim_max = 0.0
    points = payload.get("scoring_points")
    if isinstance(points, list):
        for row in points:
            if isinstance(row, dict):
                dim_sum += _point_earned_value(row)
                dim_max += _point_max_value(row, 0.0)
    if dim_sum > 0:
        return dim_sum, dim_max

    for row in payload.get("dimension_scores") or []:
        if isinstance(row, dict):
            dim_sum += _to_float(row.get("earned") or row.get("score"))
            dim_max += _to_float(row.get("max") or row.get("max_score"), 0.0)
    if dim_sum > 0:
        return dim_sum, dim_max

    section = _payload_section(payload, "分项评分", "dimensions")
    for row in _dimension_rows(section):
        dim_sum += _to_float(row.get("earned") or row.get("得分") or row.get("score"))
        dim_max += _to_float(row.get("max") or row.get("满分") or row.get("max_score"), 0.0)
    return dim_sum, dim_max


def sync_scoring_points_earned_from_llm(payload: dict[str, Any]) -> None:
    """引擎某维分为 0 但主评 dimension_scores/分项评分有分时，按维回填 scoring_points。"""
    points = payload.get("scoring_points")
    if not isinstance(points, list) or not points:
        return

    alt: list[dict[str, Any]] = []
    for row in payload.get("dimension_scores") or []:
        if isinstance(row, dict):
            alt.append(row)
    if not alt:
        section = _payload_section(payload, "分项评分", "dimensions")
        alt = [r for r in _dimension_rows(section) if isinstance(r, dict)]
    if not alt:
        return

    by_id: dict[str, dict[str, Any]] = {}
    by_label: dict[str, dict[str, Any]] = {}
    for row in alt:
        rid = str(row.get("id") or "").strip()
        lab = str(row.get("dimension") or row.get("label") or row.get("评分维度") or "").strip()
        if rid:
            by_id[rid] = row
        if lab:
            by_label[lab] = row

    for pt in points:
        if not isinstance(pt, dict):
            continue
        if _point_earned_value(pt) > 0:
            continue
        ref = by_id.get(str(pt.get("id") or "").strip()) or by_label.get(str(pt.get("label") or "").strip())
        if not ref:
            continue
        earned = _to_float(ref.get("earned") or ref.get("score") or ref.get("得分"))
        mx = _point_max_value(ref, _point_max_value(pt, 10.0))
        if earned > 0:
            pt["earned"] = earned
            pt["dimension_score_source"] = "llm_backfill"
        if mx > 0:
            pt["max"] = mx
        reason = str(ref.get("reason") or ref.get("主要原因") or ref.get("说明") or "").strip()
        if reason:
            pt["reason"] = reason


def reconcile_scoring_points_to_total(payload: dict[str, Any], *, tolerance: float = 1.5) -> None:
    """各维度 earned 加总与 total_score 不一致时，按报告总分等比校准（仅展示层）。"""
    sync_scoring_points_earned_from_llm(payload)
    points = payload.get("scoring_points")
    if not isinstance(points, list) or not points:
        return
    try:
        total = float(payload.get("total_score") or 0)
    except (TypeError, ValueError):
        return
    if total <= 0:
        return
    dim_sum = 0.0
    for row in points:
        if isinstance(row, dict):
            dim_sum += _point_earned_value(row)
    if dim_sum <= 0:
        weight_sum = sum(_point_max_value(r, 0.0) for r in points if isinstance(r, dict))
        if weight_sum > 0:
            for row in points:
                if not isinstance(row, dict):
                    continue
                mx = _point_max_value(row, 0.0)
                row["earned"] = round(total * mx / weight_sum, 1)
                row["hit"] = _infer_hit_from_earned(row["earned"], mx if mx > 0 else 10.0)
            payload["score_reconcile_note"] = (
                f"各维度原始加总不可用，已按题目满分结构将报告总分 {total} 分摊至各维度（仅展示）。"
            )
        return
    if abs(dim_sum - total) <= tolerance:
        return
    scale = total / dim_sum
    for row in points:
        if not isinstance(row, dict):
            continue
        mx = _point_max_value(row, 0.0)
        earned = _point_earned_value(row) * scale
        if mx > 0:
            earned = min(mx, earned)
        row["earned"] = round(earned, 1)
        row["hit"] = _infer_hit_from_earned(row["earned"], mx if mx > 0 else 10.0)
    payload["dimension_sum_before_reconcile"] = round(dim_sum, 1)
    payload["score_reconcile_note"] = (
        f"各维度原始加总约 {round(dim_sum, 1)} 分，已与报告采用总分 {total} 分校准一致。"
    )


def sanitize_evidence_chain(payload: dict[str, Any], *, essay_max: float = 40.0) -> None:
    """证据链单项分值不应误用整卷满分（避免展示成「总分 29/40」）。"""
    cap = max(3.0, essay_max * 0.3)
    chain = payload.get("evidence_chain")
    if not isinstance(chain, list):
        return
    for row in chain:
        if not isinstance(row, dict):
            continue
        try:
            mx = float(row.get("max") or 0)
            er = float(row.get("earned") or 0)
        except (TypeError, ValueError):
            continue
        if mx <= 0:
            continue
        if mx >= essay_max * 0.45:
            scale = cap / mx
            row["max"] = round(cap, 1)
            row["earned"] = round(min(er * scale, cap), 1)
        elif mx > cap:
            row["max"] = round(cap, 1)
            row["earned"] = round(min(er, cap), 1)
        else:
            row["earned"] = round(min(er, mx), 1)


def refresh_evidence_chain(payload: dict[str, Any]) -> None:
    from app.services.scoring_engine.report_adapter import evidence_chain_from_hit_dicts

    eng = payload.get("scoring_engine")
    if not isinstance(eng, dict):
        return
    hits = eng.get("point_hits")
    if not isinstance(hits, list) or not hits:
        return
    rebuilt = evidence_chain_from_hit_dicts(hits)
    if rebuilt:
        payload["evidence_chain"] = rebuilt


def refresh_scoring_basis_fields(payload: dict[str, Any]) -> None:
    """同步 scoring_basis 与顶层 rule/llm 分，供「查看评分依据」展示。"""
    total = display_total_score(payload)
    if total > 0:
        payload["total_score"] = total

    primary = resolved_primary_llm_score(payload)
    if primary > 0:
        payload["primary_llm_score"] = primary
        try:
            llm = float(payload.get("llm_score") or 0)
        except (TypeError, ValueError):
            llm = 0.0
        if llm <= 0:
            payload["llm_score"] = primary

    try:
        rule = float(payload.get("rule_score") or payload.get("deterministic_score") or 0)
    except (TypeError, ValueError):
        rule = 0.0
    payload["rule_score"] = rule

    stored = dict(payload.get("scoring_basis") or {})
    stored["rule_score"] = rule
    if primary > 0:
        stored["primary_llm_score"] = primary
        stored["llm_score"] = payload.get("llm_score", primary)
    for key in (
        "consensus_scores",
        "consensus_delta",
        "consensus_discarded",
        "consensus_rate",
        "confidence",
        "confidence_note",
        "confidence_scope",
        "evidence_chain",
        "engine_total_discarded",
        "score_confidence_declaration",
        "standard_version",
        "exam_standard_version",
        "grading_standard_mode",
        "scoring_points_rubric",
    ):
        if payload.get(key) is not None:
            stored[key] = payload.get(key)
        elif stored.get(key) is not None:
            payload[key] = stored[key]
    payload["scoring_basis"] = stored
    refresh_evidence_chain(payload)
    try:
        essay_max = float(payload.get("max_score") or 40)
    except (TypeError, ValueError):
        essay_max = 40.0
    strip_holistic_dimension_rows(payload)
    reconcile_scoring_points_to_total(payload)
    sync_scoring_points_hit_from_earned(payload)
    sanitize_evidence_chain(payload, essay_max=essay_max)
    if primary > 0:
        payload["primary_llm_score"] = primary
        payload["llm_score"] = payload.get("llm_score") or primary
        stored["primary_llm_score"] = primary
        stored["llm_score"] = payload["llm_score"]
        payload["scoring_basis"] = stored


def refresh_retry_comparison_scores(
    payload: dict[str, Any],
    *,
    baseline_payload: dict[str, Any] | None = None,
) -> None:
    """重作对比中的分数与涨幅与当前解析后的总分对齐。"""
    comp = payload.get("comparison")
    if not isinstance(comp, dict):
        return
    second = display_total_score(payload)
    if baseline_payload is not None:
        first = display_total_score(baseline_payload)
        comp["first_score"] = first
    else:
        first = float(comp.get("first_score") or 0)
    comp["second_score"] = second
    comp["score_delta"] = round(second - first, 1)


_ENGINE_DIM_REASON = "确定性引擎按采分点覆盖率聚合"


def _issues_are_placeholder(issues: Any) -> bool:
    if not isinstance(issues, list) or not issues:
        return True
    for item in issues:
        if not isinstance(item, dict):
            continue
        exp = str(item.get("explanation") or "").strip()
        tag = str(item.get("tag") or "").strip()
        if len(exp) >= 8 and tag not in ("作答问题", ""):
            return False
        if tag.startswith("Q") or (tag and tag not in ("作答问题",) and len(tag) <= 16):
            if exp:
                return False
    return True


def _scoring_points_engine_only(points: Any) -> bool:
    if not isinstance(points, list) or not points:
        return True
    for pt in points:
        if not isinstance(pt, dict):
            continue
        reason = str(pt.get("reason") or "").strip()
        if reason and reason != _ENGINE_DIM_REASON:
            return False
    return bool(points)


_ISSUE_SEVERITY_RANK: dict[str, int] = {"severe": 3, "moderate": 2, "minor": 1}

_RETRY_POLICY_MESSAGE = (
    "改写后「主要问题」仅保留轻微档残留项；下列中等及以上问题须继续修改后再提交。"
)


def _severity_from_level(level: str) -> str:
    if "A级" in level or "严重" in level:
        return "severe"
    if "C级" in level or "一般" in level or "轻微" in level:
        return "minor"
    if "中等" in level or "B级" in level:
        return "moderate"
    return "moderate"


def normalize_issue_severity(item: dict[str, Any]) -> str:
    raw = str(item.get("severity") or "").strip().lower()
    if raw in _ISSUE_SEVERITY_RANK:
        return raw
    level = str(item.get("level") or item.get("等级") or "")
    if level.strip():
        return _severity_from_level(level)
    return "moderate"


def _core_problem_row_limit(payload: dict[str, Any]) -> int:
    return 8 if int(payload.get("attempt") or 1) <= 1 else 4


def enforce_retry_issue_severity_policy(
    payload: dict[str, Any],
    *,
    comparison: dict[str, Any] | None = None,
) -> None:
    """
    重作批改（attempt≥2）：主要问题只接受轻微档。
    中等/严重项移入 retry_major_issues；结合 comparison 防止模型把未改问题标成轻微。
    """
    if int(payload.get("attempt") or 1) < 2:
        payload.pop("retry_major_issues", None)
        payload.pop("retry_issue_policy_ok", None)
        payload.pop("retry_issue_policy_message", None)
        return

    from app.services.coach_service import _issue_comparison_key

    change_by_key: dict[str, str] = {}
    for row in (comparison or {}).get("issue_changes") or []:
        if isinstance(row, dict) and row.get("tag") and row.get("status"):
            change_by_key[str(row["tag"])] = str(row["status"])

    accepted: list[dict[str, Any]] = []
    major: list[dict[str, Any]] = []

    for item in payload.get("issues") or []:
        if not isinstance(item, dict):
            continue
        key = _issue_comparison_key(item)
        status = change_by_key.get(key) if key else None
        rank = _ISSUE_SEVERITY_RANK.get(normalize_issue_severity(item), 2)

        if status in ("unchanged", "worse"):
            major.append(item)
            continue
        if status == "new" and rank >= 2:
            major.append(item)
            continue
        if rank >= 2:
            major.append(item)
            continue
        accepted.append(item)

    payload["issues"] = accepted
    if major:
        payload["retry_major_issues"] = major
        payload["retry_issue_policy_ok"] = False
        payload["retry_issue_policy_message"] = _RETRY_POLICY_MESSAGE
    else:
        payload.pop("retry_major_issues", None)
        payload["retry_issue_policy_ok"] = True
        payload.pop("retry_issue_policy_message", None)

    core = payload.get("core_problems")
    if isinstance(core, list):
        kept: list[Any] = []
        for row in core:
            if not isinstance(row, dict):
                continue
            if _ISSUE_SEVERITY_RANK.get(_severity_from_level(str(row.get("level") or "")), 2) >= 2:
                continue
            kept.append(row)
        payload["core_problems"] = kept


def compact_display_issues(payload: dict[str, Any], *, max_items: int = 5) -> None:
    """合并完全重复的问题行，控制主要问题列表长度。"""
    issues = payload.get("issues")
    if not isinstance(issues, list) or len(issues) <= 1:
        return
    from app.domain.essay import normalize_issue_code

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in issues:
        if not isinstance(item, dict):
            continue
        code = normalize_issue_code(item.get("tag"))
        title = str(item.get("issue_title") or "").strip()
        quote = str(item.get("user_quote") or "")[:40]
        key = "|".join(x for x in (code, title, quote) if x)
        if not key:
            key = str(item.get("explanation") or "")[:48]
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= max_items:
            break
    payload["issues"] = out


def prior_core_problems_for_retry(baseline_payload: dict[str, Any]) -> list[dict[str, str]]:
    """上一稿核心问题摘要，供重作批改 prompt 对照。"""
    hydrated = dict(baseline_payload)
    hydrate_report_display_fields(hydrated)
    items: list[dict[str, str]] = []
    for row in hydrated.get("core_problems") or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        problem = str(row.get("problem") or "").strip()
        if title or problem:
            items.append({"title": title, "problem": problem})
    if items:
        return items[:6]
    for row in hydrated.get("issues") or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("issue_title") or row.get("tag") or "").strip()
        problem = str(row.get("explanation") or "").strip()
        if title or problem:
            items.append({"title": title, "problem": problem})
    return items[:6]


def hydrate_report_display_fields(payload: dict[str, Any]) -> None:
    """
    主评 JSON 使用 dimension_scores / core_problems / revision_priority 等扩展键时，
    映射为报告页使用的 scoring_points、issues、suggestions、review_notes。
    """
    dimension_scores = payload.get("dimension_scores")
    if isinstance(dimension_scores, list) and dimension_scores:
        pts = payload.get("scoring_points")
        pts_sum = 0.0
        if isinstance(pts, list):
            pts_sum = sum(_point_earned_value(r) for r in pts if isinstance(r, dict))
        if _scoring_points_engine_only(pts) or pts_sum <= 0:
            points: list[dict[str, Any]] = []
            for i, row in enumerate(dimension_scores):
                if not isinstance(row, dict):
                    continue
                earned = _to_float(row.get("earned") or row.get("score"))
                mx = _to_float(row.get("max") or row.get("max_score"), 10.0)
                label = str(row.get("dimension") or row.get("label") or f"维度{i + 1}")
                reason = str(row.get("reason") or row.get("说明") or "").strip()
                points.append(
                    {
                        "id": row.get("id") or f"D{i + 1:02d}",
                        "label": label,
                        "earned": earned,
                        "max": mx,
                        "hit": _infer_hit(earned, mx),
                        "reason": reason,
                    }
                )
            if points:
                payload["scoring_points"] = points

    sync_scoring_points_hit_from_earned(payload)

    core_problems = payload.get("core_problems")
    if isinstance(core_problems, list) and core_problems and _issues_are_placeholder(payload.get("issues")):
        issues: list[dict[str, Any]] = []
        for row in core_problems[: _core_problem_row_limit(payload)]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            problem = str(row.get("problem") or "").strip()
            impact = str(row.get("impact") or "").strip()
            revision = str(row.get("revision") or "").strip()
            explanation = problem
            if impact:
                explanation = f"{problem} {impact}".strip() if problem else impact
            if not explanation and revision:
                explanation = revision
            issues.append(
                {
                    "tag": issue_tag_from_core_problem(title, problem),
                    "issue_title": title or None,
                    "severity": _severity_from_level(str(row.get("level") or "")),
                    "explanation": explanation or title,
                    "user_quote": str(row.get("original") or "")[:240],
                }
            )
        if issues:
            payload["issues"] = issues

    if not payload.get("suggestions"):
        suggestions: list[str] = []
        revision_priority = payload.get("revision_priority")
        if isinstance(revision_priority, dict):
            block = revision_priority.get("if_only_three_changes") or revision_priority.get("items")
            if isinstance(block, list):
                suggestions.extend(str(x).strip() for x in block if str(x).strip())
        if not suggestions and isinstance(core_problems, list):
            for row in core_problems[:5]:
                if isinstance(row, dict) and row.get("revision"):
                    suggestions.append(str(row["revision"]).strip())
        payload["suggestions"] = suggestions[:8]

    if not str(payload.get("review_notes") or "").strip():
        grade = str(payload.get("grade") or "").strip()
        overall = str(payload.get("overall_comment") or payload.get("overall") or "").strip()
        if grade and overall:
            payload["review_notes"] = f"{grade}。{overall}"
        elif grade:
            payload["review_notes"] = grade
        elif overall:
            payload["review_notes"] = overall


def overlay_llm_dimension_reasons(payload: dict[str, Any]) -> None:
    """分层批改时若展示分来自引擎，仍尽量保留主评「分项评分」中的维度说明。"""
    section = _payload_section(payload, "分项评分", "dimensions")
    rows = _dimension_rows(section)
    if not rows:
        return
    by_label: dict[str, str] = {}
    for row in rows:
        label = str(row.get("label") or row.get("评分维度") or row.get("name") or "").strip()
        reason = str(row.get("reason") or row.get("主要原因") or row.get("说明") or "").strip()
        if label and reason and reason != _ENGINE_DIM_REASON:
            by_label[label] = reason
    if not by_label:
        return
    points = payload.get("scoring_points")
    if not isinstance(points, list):
        return
    for pt in points:
        if not isinstance(pt, dict):
            continue
        lab = str(pt.get("label") or "").strip()
        cur = str(pt.get("reason") or "").strip()
        if lab in by_label and (not cur or cur == _ENGINE_DIM_REASON):
            pt["reason"] = by_label[lab]


_ISSUE_QUOTE_HINTS: dict[str, tuple[str, ...]] = {
    "Q22": ("从", "层面", "长期", "价值", "论"),
    "Q24": ("例如", "比如", "A市", "F银行", "L市", "S市", "据", "材料"),
    "Q25": ("首先", "其次", "一方面", "另一方面", "从"),
    "Q17": ("值得", "毋庸置疑", "日益", "关乎", "在"),
    "Q21": ("价值", "立意", "观点", "论"),
    "Q23": ("例如", "比如", "案例", "材料"),
}


def _issue_code_from_tag(tag: str) -> str:
    m = re.match(r"(Q\d+)", tag or "", re.I)
    return m.group(1).upper() if m else ""


def _essay_sentences(essay: str) -> list[str]:
    parts = re.split(r"[。！？!?；;\n]+", essay.replace("\r\n", "\n"))
    return [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) >= 8]


def _paragraph_excerpt_from_ref(essay: str, material_ref: str) -> str:
    m = re.search(r"第\s*(\d+)\s*段", material_ref or "")
    if not m:
        return ""
    want = int(m.group(1))
    if want < 1:
        return ""
    normalized = essay.replace("\r\n", "\n")
    para_starts: list[tuple[int, int]] = []
    cursor = 0
    after_blank = True
    for line in normalized.split("\n"):
        start = cursor
        end = start + len(line)
        cursor = end + 1
        if not line.strip():
            after_blank = True
            continue
        if after_blank:
            para_starts.append((start, end))
            after_blank = False
        else:
            after_blank = False
    if want > len(para_starts):
        return ""
    p_start, p_end = para_starts[want - 1]
    if want < len(para_starts):
        p_end = para_starts[want][0] - 1
    else:
        p_end = len(normalized)
    text = re.sub(r"\s+", " ", normalized[p_start:p_end]).strip()
    return text[:160] if len(text) > 160 else text


def _trim_mid_excerpt(text: str, max_len: int = 120) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= max_len:
        return t
    half = max_len // 2 - 2
    return f"{t[:half]}……{t[-half:]}"


def _quote_verified_in_essay(quote: str, essay: str) -> bool:
    q = quote.strip()
    if len(q) < 4:
        return False
    if q in essay:
        return True
    q_collapsed = re.sub(r"\s+", "", q)
    essay_collapsed = re.sub(r"\s+", "", essay)
    return len(q_collapsed) >= 4 and q_collapsed in essay_collapsed


def _quoted_fragments_in_problem(text: str) -> list[str]:
    raw = [m.strip() for m in re.findall(r"[「『]([^」』]{4,48})[」』]", text or "") if m.strip()]
    out: list[str] = []
    seen: set[str] = set()
    for frag in raw:
        for piece in (frag, *re.split(r"[…\.]{2,}", frag)):
            piece = piece.strip("，、；： ")
            if len(piece) < 4 or piece in seen:
                continue
            seen.add(piece)
            out.append(piece)
    return out


def _issue_should_anchor_from_explanation(prob: str) -> bool:
    if _quoted_fragments_in_problem(prob):
        return True
    return bool(re.search(r"3\.\s*|误输入|格式残留|格式错误|模版|模板|套话|模版化", prob or ""))


def _find_phrase_pos_in_essay(essay: str, phrase: str) -> int:
    phrase = phrase.strip()
    if not phrase:
        return -1
    idx = essay.find(phrase)
    if idx >= 0:
        return idx
    pc = re.sub(r"\s+", "", phrase)
    ec = re.sub(r"\s+", "", essay)
    if len(pc) < 4 or pc not in ec:
        return -1
    ci = ec.find(pc)
    if ci < 0:
        return -1
    raw = 0
    col = 0
    while raw < len(essay) and col < ci:
        if not essay[raw].isspace():
            col += 1
        raw += 1
    return raw


def _sentence_containing_pos(essay: str, pos: int) -> str:
    pos = max(0, min(len(essay), pos))
    left = max(
        essay.rfind("。", pos),
        essay.rfind("！", pos),
        essay.rfind("？", pos),
        essay.rfind("；", pos),
        essay.rfind("\n", pos),
    )
    start = 0 if left < 0 else left + 1
    ends = [essay.find(ch, pos) for ch in "。！？；\n"]
    ends = [x for x in ends if x >= 0]
    end = (min(ends) + 1) if ends else len(essay)
    return re.sub(r"\s+", " ", essay[start:end]).strip()


def _closing_template_sentence_in_essay(essay: str) -> str:
    for m in re.finditer(
        r"[^。！？\n]{0,24}方能[^。！？\n]{0,36}共建[^。！？\n]{0,36}美[^。！？\n]{0,24}[。！？]",
        essay,
    ):
        sent = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(sent) >= 12:
            return _trim_mid_excerpt(sent, 200)
    for m in re.finditer(r"[^。！？\n]{0,12}共建[^。！？\n]{0,36}美[^。！？\n]{0,24}生活[^。！？\n]{0,12}[。！？]", essay):
        sent = re.sub(r"\s+", " ", m.group(0)).strip()
        if len(sent) >= 12:
            return _trim_mid_excerpt(sent, 200)
    return ""


def _issue_anchor_spans_from_explanation(essay: str, issue: dict[str, Any]) -> list[tuple[int, int]]:
    prob = f"{issue.get('explanation') or ''} {issue.get('issue_title') or ''}"
    if not _issue_should_anchor_from_explanation(prob):
        return []
    essay = (essay or "").strip()
    if not essay:
        return []
    spans: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    def add_span(start: int, end: int) -> None:
        if end <= start:
            return
        key = (start, end)
        if key in seen:
            return
        seen.add(key)
        spans.append(key)

    for phrase in _quoted_fragments_in_problem(prob):
        pos = _find_phrase_pos_in_essay(essay, phrase)
        if pos < 0:
            continue
        sent = _sentence_containing_pos(essay, pos)
        loc = _locate_quote_span(essay, sent) if sent else None
        if loc:
            add_span(loc[0], loc[1])

    if re.search(r"模板|套话|模版|方能|口号", prob):
        closing = _closing_template_sentence_in_essay(essay)
        if closing:
            loc = _locate_quote_span(essay, closing)
            if loc:
                add_span(loc[0], loc[1])

    if re.search(r"3\.\s*|误输入|格式残留|格式错误", prob):
        m = re.search(r"(?:^|[\n\r])\s*3\.\s*[^\n\r。！？；]{4,}", essay)
        if m:
            line = m.group(0).strip()
            idx = essay.find(line)
            if idx >= 0:
                add_span(idx, idx + len(line))

    return spans


def resolve_issue_anchor_from_explanation(essay: str, issue: dict[str, Any]) -> str:
    """问题说明中点名的套话/误输等在正文中的对应句，优先于无关 user_quote。"""
    prob = f"{issue.get('explanation') or ''} {issue.get('issue_title') or ''}"
    if not _issue_should_anchor_from_explanation(prob):
        return ""
    essay = (essay or "").strip()
    if not essay:
        return ""

    span_list = _issue_anchor_spans_from_explanation(essay, issue)
    if span_list:
        start, end = span_list[0]
        return _trim_mid_excerpt(essay[start:end], 200)

    for tpl in (
        "方能共建温暖、安定、美好的生活家园",
        "方能共建温暖、稳定、美好的生活家园",
        "共建温暖、安定、美好的生活家园",
        "共建温暖、稳定、美好的生活家园",
    ):
        if tpl in prob and tpl in essay:
            return _trim_mid_excerpt(_sentence_containing_pos(essay, essay.find(tpl)), 200)

    if re.search(r"模板|套话|模版|方能", prob):
        closing = _closing_template_sentence_in_essay(essay)
        if closing:
            return closing

    return ""


def _locate_quote_span(essay: str, quote: str) -> tuple[int, int] | None:
    q = quote.strip()
    if len(q) < 4:
        return None
    idx = essay.find(q)
    if idx >= 0:
        return idx, idx + len(q)
    for length in range(min(len(q), 56), 7, -2):
        sub = q[:length]
        idx = essay.find(sub)
        if idx >= 0:
            return idx, idx + length
    q_collapsed = re.sub(r"\s+", "", q)
    essay_collapsed = re.sub(r"\s+", "", essay)
    if len(q_collapsed) >= 4 and q_collapsed in essay_collapsed:
        ci = essay_collapsed.find(q_collapsed)
        raw = 0
        col = 0
        while raw < len(essay) and col < ci:
            if not essay[raw].isspace():
                col += 1
            raw += 1
        return raw, min(len(essay), raw + len(q))
    return None


def _quote_plausible_for_explanation(prob: str, quote: str, essay: str) -> bool:
    """说明已点名具体片段时，拒绝与说明无关的长段 user_quote。"""
    if not _issue_should_anchor_from_explanation(prob):
        return True
    quote = quote.strip()
    if not quote or not _quote_verified_in_essay(quote, essay):
        return False
    anchors = _issue_anchor_spans_from_explanation(essay, {"explanation": prob, "issue_title": ""})
    if not anchors:
        return True
    qloc = _locate_quote_span(essay, quote)
    if not qloc:
        return False
    qs, qe = qloc
    for start, end in anchors:
        if qs <= end and qe >= start:
            return True
    return len(quote) <= 48


def _infer_issue_user_quote(essay: str, issue: dict[str, Any], taken: set[str]) -> str:
    prob = f"{issue.get('explanation') or ''} {issue.get('issue_title') or ''}"
    if _issue_should_anchor_from_explanation(prob):
        anchor = resolve_issue_anchor_from_explanation(essay, issue)
        if anchor:
            key = anchor[:48]
            if key not in taken:
                taken.add(key)
            return anchor

    para_m = re.search(r"第\s*(\d+)\s*段", prob)
    if para_m:
        para = _paragraph_excerpt_from_ref(essay, f"第{para_m.group(1)}段")
        if para:
            key = para[:48]
            if key not in taken:
                taken.add(key)
            return _trim_mid_excerpt(para, 120)

    quote = str(issue.get("user_quote") or "").strip()
    if quote and _quote_verified_in_essay(quote, essay) and _quote_plausible_for_explanation(prob, quote, essay):
        key = quote[:48]
        if key not in taken:
            taken.add(key)
        return _trim_mid_excerpt(quote, 120)

    ref = str(issue.get("material_ref") or issue.get("evidence_ref") or "")
    para = _paragraph_excerpt_from_ref(essay, ref)
    if para:
        key = para[:48]
        if key not in taken:
            taken.add(key)
            return _trim_mid_excerpt(para, 120)

    hints = _ISSUE_QUOTE_HINTS.get(_issue_code_from_tag(str(issue.get("tag") or "")), ())
    best, best_score = "", 0
    for sent in _essay_sentences(essay):
        key = sent[:48]
        if key in taken:
            continue
        score = min(len(sent), 80) // 25
        for h in hints:
            if h in sent:
                score += 3
        if score > best_score:
            best_score, best = score, sent
    if best_score >= 3 and best:
        taken.add(best[:48])
        return _trim_mid_excerpt(best, 120)

    for sent in _essay_sentences(essay):
        key = sent[:48]
        if key in taken:
            continue
        if len(sent) >= 16:
            taken.add(key)
            return _trim_mid_excerpt(sent, 120)
    return ""


def _enrich_scoring_point_quotes(payload: dict[str, Any], essay: str) -> None:
    chain = payload.get("evidence_chain")
    if not isinstance(chain, list):
        chain = []
    points = payload.get("scoring_points")
    if not isinstance(points, list):
        return
    for pt in points:
        if not isinstance(pt, dict):
            continue
        existing = str(pt.get("user_quote") or "").strip()
        if existing and _quote_verified_in_essay(existing, essay):
            pt["user_quote"] = _trim_mid_excerpt(existing, 120)
            continue
        lab = str(pt.get("label") or "").strip()
        for row in chain:
            if not isinstance(row, dict):
                continue
            row_lab = str(row.get("label") or "").strip()
            if not lab or not row_lab:
                continue
            if lab != row_lab and lab not in row_lab and row_lab not in lab:
                continue
            uq = str(row.get("user_quote") or "").strip()
            if uq and _quote_verified_in_essay(uq, essay):
                pt["user_quote"] = _trim_mid_excerpt(uq, 120)
                break
        if pt.get("user_quote"):
            continue
        ref = str(pt.get("evidence_ref") or pt.get("material_ref") or "")
        para = _paragraph_excerpt_from_ref(essay, ref)
        if para:
            pt["user_quote"] = para
            continue
        ev = str(pt.get("evidence_ref") or "").strip()
        if ev and not re.match(r"^材料", ev) and _quote_verified_in_essay(ev, essay):
            pt["user_quote"] = _trim_mid_excerpt(ev, 120)


def enrich_report_essay_quotes(payload: dict[str, Any], essay: str) -> None:
    """为问题/维度补全可在正文中核验的 user_quote（报告展示用，不写库）。"""
    essay = (essay or "").strip()
    if not essay:
        return
    taken: set[str] = set()
    for key in ("issues", "retry_major_issues"):
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for issue in items:
            if not isinstance(issue, dict):
                continue
            q = _infer_issue_user_quote(essay, issue, taken)
            if q:
                issue["user_quote"] = q
            elif issue.get("user_quote") and not _quote_verified_in_essay(
                str(issue.get("user_quote")), essay
            ):
                issue.pop("user_quote", None)
    _enrich_scoring_point_quotes(payload, essay)


def _try_parse_loose_dict(text: str) -> dict[str, Any] | None:
    import ast
    import json

    s = text.strip()
    if not s.startswith("{"):
        return None
    try:
        obj = ast.literal_eval(s)
        return obj if isinstance(obj, dict) else None
    except (SyntaxError, ValueError):
        pass
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _format_suggestion_dict(row: dict[str, Any]) -> str:
    content = str(
        row.get("内容") or row.get("content") or row.get("text") or row.get("建议") or row.get("suggestion") or ""
    ).strip()
    reason = str(row.get("原因") or row.get("reason") or "").strip()
    if content and reason:
        return f"{content}（{reason}）"
    return content or reason


def suggestion_to_display_text(item: Any) -> str:
    if isinstance(item, dict):
        return _format_suggestion_dict(item) or ""
    if isinstance(item, str):
        s = item.strip()
        if not s:
            return ""
        if s.startswith("{") and ("内容" in s or "content" in s):
            parsed = _try_parse_loose_dict(s)
            if parsed:
                formatted = _format_suggestion_dict(parsed)
                if formatted:
                    return formatted
        return s
    if item is None:
        return ""
    return str(item).strip()


def normalize_suggestions_field(payload: dict[str, Any]) -> None:
    raw = payload.get("suggestions")
    if not isinstance(raw, list):
        return
    out = [suggestion_to_display_text(x) for x in raw]
    payload["suggestions"] = [t for t in out if t][:8]


def normalize_llm_report_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """
    将模型返回的非标准 JSON（常见中文键、兼容模式）映射为报告页使用的英文字段。
    保留原始键，便于「评分依据」排查。
    """
    payload = dict(raw)
    final_block = payload.get("最终得分")
    if isinstance(final_block, dict):
        parsed_final = _parse_score_value(final_block.get("分数"))
        if parsed_final is not None and parsed_final >= 0:
            current = payload.get("total_score")
            try:
                current_num = float(current) if current is not None else None
            except (TypeError, ValueError):
                current_num = None
            if current_num is None or current_num <= 0:
                payload["total_score"] = parsed_final

    summary = _payload_section(payload, "综合评分")
    if isinstance(summary, dict):
        parsed = _parse_score_value(summary.get("总分"))
        if parsed is not None and parsed >= 0:
            current = payload.get("total_score")
            try:
                current_num = float(current) if current is not None else None
            except (TypeError, ValueError):
                current_num = None
            if current_num is None or (current_num <= 0 and parsed > 0):
                payload["total_score"] = parsed

    section_scores = _payload_section(payload, "分项评分", "dimensions")
    if not payload.get("scoring_points"):
        rows = _dimension_rows(section_scores)
        if not rows and isinstance(section_scores, list):
            rows = _dimension_rows(section_scores)
        points: list[dict[str, Any]] = []
        essay_max = _essay_max_from_payload(payload)
        for i, row in enumerate(rows):
            earned = _to_float(row.get("earned") or row.get("得分") or row.get("score"))
            mx = _to_float(row.get("max") or row.get("满分") or row.get("max_score"), 10.0)
            label = row.get("label") or row.get("评分维度") or row.get("name") or f"维度{i + 1}"
            if is_holistic_dimension_row(str(label), mx, essay_max=essay_max) and len(rows) > 1:
                continue
            points.append(
                {
                    "id": row.get("id") or f"D{i + 1:02d}",
                    "label": str(label),
                    "earned": earned,
                    "max": mx,
                    "hit": _infer_hit(earned, mx),
                    "reason": row.get("reason") or row.get("主要原因") or row.get("说明") or "",
                    "evidence_ref": row.get("evidence_ref") or row.get("material_ref"),
                }
            )
        payload["scoring_points"] = points

    sync_scoring_points_hit_from_earned(payload)

    if not payload.get("issues"):
        issues: list[dict[str, Any]] = []
        for row in _issue_rows(payload)[:5]:
            problem = str(row.get("问题") or row.get("explanation") or "").strip()
            raw_tag = str(row.get("tag") or "").strip()
            if raw_tag and re.match(r"^问题\s*\d+$", raw_tag):
                raw_tag = ""
            why = str(row.get("为什么扣分") or "").strip()
            explanation = str(row.get("explanation") or problem).strip()
            if why and why not in explanation:
                explanation = f"{explanation} {why}".strip() if explanation else why
            issues.append(
                {
                    "tag": resolve_issue_badge(problem, raw_tag or None),
                    "severity": row.get("severity") or "moderate",
                    "explanation": explanation,
                    "user_quote": row.get("user_quote") or row.get("原文表现") or "",
                }
            )
        payload["issues"] = issues

    if not payload.get("suggestions"):
        suggestions: list[str] = []
        prio = _payload_section(payload, "修改优先级")
        if isinstance(prio, dict):
            for key, block in prio.items():
                if isinstance(block, list) and ("改" in key or "建议" in key or key in ("items", "优先修改")):
                    suggestions.extend(suggestion_to_display_text(x) for x in block)
        for row in _issue_rows(payload):
            fix = row.get("如何改") or row.get("修改建议") or row.get("修改方向")
            if fix:
                suggestions.append(str(fix))
        payload["suggestions"] = suggestions[:8]

    if isinstance(summary, dict):
        excerpt = _summary_review_text(summary)
        if excerpt and not payload.get("review_notes"):
            payload["review_notes"] = excerpt

    resolve_review_notes_excerpt(payload)

    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        exp = str(issue.get("explanation") or "").strip()
        tag = str(issue.get("tag") or "").strip()
        if not exp and not tag:
            continue
        if len(tag) > 18 or re.match(r"^问题\s*\d+$", tag) or not re.match(r"^Q\d+\s", tag, re.I):
            issue["tag"] = resolve_issue_badge(exp or tag, tag if re.match(r"^Q\d+", tag, re.I) else None)

    hydrate_report_display_fields(payload)
    normalize_suggestions_field(payload)
    return payload


def refresh_requirement_scoring_summary(payload: dict[str, Any], prompt: str) -> None:
    """按作答要求刷新「题目分值/字数/材料」对照（报告 GET 与批改完成时调用）。"""
    from app.domain.requirement_scoring import build_requirement_scoring_summary

    meta = payload.get("essay_meta") or {}
    display_ref = payload.get("display_mode") == "reference_only"
    total = float(payload.get("total_score") or 0)
    dim_sum, dim_max = dimension_earned_totals(payload)
    from app.domain.requirement_scoring import refresh_score_display_context

    refresh_score_display_context(payload, prompt)
    display_max = float(payload.get("display_max_score") or payload.get("max_score") or 40)
    payload["requirement_scoring"] = build_requirement_scoring_summary(
        prompt,
        max_score=display_max,
        word_min=int(meta.get("word_min") or 800),
        word_max=int(meta.get("word_max") or 1200),
        essay_char_count=int(meta.get("essay_char_count") or 0),
        word_ratio=float(meta.get("word_ratio") or 0),
        total_score=total,
        dimension_sum=dim_sum,
        dimension_max=dim_max,
        has_user_material=bool(meta.get("has_user_material")),
        display_reference_only=display_ref,
    )


def build_scoring_basis(payload: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    essay_meta = payload.get("essay_meta") or {}
    return {
        "rule_score": payload.get("rule_score"),
        "llm_score": payload.get("llm_score"),
        "consensus_scores": payload.get("consensus_scores"),
        "consensus_rate": payload.get("consensus_rate"),
        "confidence": payload.get("confidence"),
        "scoring_points_rubric": question.get("scoring_points"),
        "steps_summary": payload.get("review_notes"),
        "standard_version": payload.get("standard_version") or essay_meta.get("standard_version"),
        "exam_standard_version": payload.get("exam_standard_version") or essay_meta.get("exam_standard_version"),
        "grading_standard_mode": essay_meta.get("grading_standard_mode"),
        "consensus_discarded": payload.get("consensus_discarded"),
        "consensus_delta": payload.get("consensus_delta"),
        "primary_llm_score": payload.get("primary_llm_score"),
        "confidence_note": payload.get("confidence_note"),
        "confidence_scope": payload.get("confidence_scope"),
        "evidence_chain": payload.get("evidence_chain"),
        "engine_total_discarded": payload.get("engine_total_discarded"),
        "score_confidence_declaration": (payload.get("essay_meta") or {}).get("score_confidence_declaration"),
        "exam_level": essay_meta.get("exam_level"),
        "level_inferred": essay_meta.get("level_inferred"),
    }
