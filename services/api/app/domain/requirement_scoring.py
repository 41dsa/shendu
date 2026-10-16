"""从用户「作答要求」文本解析分值、字数等约束，并对照批改结果生成展示摘要。"""

from __future__ import annotations

import re
from typing import Any, Literal

Status = Literal["ok", "warn", "fail", "info"]


def parse_requirements_from_prompt(prompt: str) -> dict[str, Any]:
    text = (prompt or "").strip()
    out: dict[str, Any] = {
        "declared_max_score": None,
        "word_min": None,
        "word_max": None,
        "requires_self_title": False,
        "requires_use_material": False,
        "requires_contact_reality": False,
    }
    if not text:
        return out

    score_hits = re.findall(r"(?:满分|共|总计|分值)?\s*(\d{1,3})\s*分", text)
    if score_hits:
        candidates = [int(x) for x in score_hits if 5 <= int(x) <= 100]
        if candidates:
            out["declared_max_score"] = max(candidates)

    range_m = re.search(r"(\d{3,4})\s*[～~\-—至到]\s*(\d{3,4})\s*字", text)
    if range_m:
        out["word_min"] = int(range_m.group(1))
        out["word_max"] = int(range_m.group(2))
    else:
        at_least = re.search(r"(?:不少于|至少|不低于)\s*(\d{3,4})\s*字", text)
        at_most = re.search(r"(?:不超过|至多|最多)\s*(\d{3,4})\s*字", text)
        if at_least:
            out["word_min"] = int(at_least.group(1))
        if at_most:
            out["word_max"] = int(at_most.group(1))

    if re.search(r"自拟.{0,4}标题|自命.{0,4}标题|标题自拟", text):
        out["requires_self_title"] = True
    if re.search(r"参考.{0,6}材料|结合.{0,6}材料|给定材料|联系材料", text):
        out["requires_use_material"] = True
    if re.search(r"联系实际", text):
        out["requires_contact_reality"] = True
    return out


def score_tier_for_total(total: float, max_score: float) -> dict[str, Any]:
    """按公考大作文四档区间（随满分缩放）判定档次。"""
    from app.domain.scoring_engine.level_config import _base_tiers

    if max_score <= 0:
        return {"tier_id": "t4", "label": "四类文", "band": "—", "full_label": "四类文"}
    tiers = _base_tiers(max_score)
    for rule in tiers:
        lo = float(rule["score_min"])
        hi = float(rule["score_max"])
        if lo <= total <= hi:
            full = str(rule["label"])
            short = full.split("（", 1)[0].strip() if "（" in full else full
            return {
                "tier_id": rule["tier_id"],
                "label": short,
                "band": f"{round(lo)}—{round(hi)}",
                "full_label": full,
            }
    last = tiers[-1]
    full = str(last["label"])
    short = full.split("（", 1)[0].strip() if "（" in full else full
    return {
        "tier_id": last["tier_id"],
        "label": short,
        "band": f"0—{round(float(last['score_max']))}",
        "full_label": full,
    }


def _is_tier_only_excerpt(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if re.match(r"^[一二三四]类文[（(]", t):
        return True
    return len(t) <= 20 and bool(re.match(r"^[一二三四]类文", t))


def canonical_tier_review_line(tier: dict[str, Any], total: float) -> str:
    full = str(tier.get("full_label") or tier.get("label") or "").strip()
    if not full:
        return ""
    if "文" not in full and tier.get("band"):
        full = f"{full}文（{tier['band']} 分）"
    return f"{full}，约{total:g}分"


_TIER_WITH_BAND_RE = re.compile(r"[一二三四]类文[（(][^）)]*[）)]")


def harmonize_review_tier_text(text: str, tier: dict[str, Any], total: float) -> str:
    """总评摘录中的档次与区间：一律按作答要求满分缩放后的四档（非系统 Rubric 满分）。"""
    tier_label = str(tier.get("label") or "").strip()
    if not text.strip() or not tier_label:
        return text
    full_label = str(tier.get("full_label") or "").strip()
    canonical = tier_label if "文" in tier_label else f"{tier_label}文"
    out = text
    if full_label:
        out = _TIER_WITH_BAND_RE.sub(full_label, out)
    for wrong in ("一类文", "二类文", "三类文", "四类文"):
        if wrong == canonical:
            continue
        out = re.sub(
            rf"(综合评[为判]?|整体[定评][为判]?|评为|定为){re.escape(wrong)}",
            rf"\1{canonical}",
            out,
        )
        out = re.sub(
            rf"([，,。；;]\s*){re.escape(wrong)}([，,]?\s*约?\s*[\d.]+\s*分)",
            rf"\1{canonical}\2",
            out,
        )
        out = out.replace(wrong, canonical)
    if full_label:
        out = _TIER_WITH_BAND_RE.sub(full_label, out)
    anchor = full_label or canonical
    out = re.sub(
        rf"({re.escape(anchor)})[，,]?\s*约?\s*[\d.]+\s*分",
        rf"\1，约{total:g}分",
        out,
        count=1,
    )
    if anchor == canonical:
        out = re.sub(
            rf"({re.escape(canonical)})[，,]?\s*约?\s*[\d.]+\s*分",
            rf"\1，约{total:g}分",
            out,
            count=1,
        )
    return out


def recompute_score_confidence_range(payload: dict[str, Any]) -> None:
    """总分置信浮动区间，与最终 total_score、display_max_score 一致（读报告/升档后重算）。"""
    try:
        total = float(payload.get("total_score") or 0)
    except (TypeError, ValueError):
        return
    if total <= 0:
        payload["score_range"] = [0, 0]
        return
    display_max = float(payload.get("display_max_score") or payload.get("max_score") or 40)
    if display_max <= 0:
        return
    conf = str(payload.get("confidence") or "medium").lower()
    span = 1.0 if conf == "high" else 2.0 if conf == "medium" else 2.5
    payload["score_range"] = [
        max(0.0, round(total - span, 1)),
        min(display_max, round(total + span, 1)),
    ]


def refresh_score_display_context(payload: dict[str, Any], prompt: str) -> None:
    """作答要求中的满分 → 展示分母、按题分四档判定，并统一总评摘录/综合评分中的档次表述。"""
    parsed = parse_requirements_from_prompt(prompt)
    declared = parsed.get("declared_max_score")
    system_max = float(payload.get("max_score") or 40)
    display_max = float(declared) if declared else system_max
    payload["display_max_score"] = display_max
    if declared and int(declared) != int(system_max):
        payload["max_score_system"] = system_max

    try:
        total = float(payload.get("total_score") or 0)
    except (TypeError, ValueError):
        total = 0.0
    if total <= 0 or display_max <= 0:
        return

    tier = score_tier_for_total(total, display_max)
    payload["grade_by_requirements"] = tier["label"]
    payload["grade_band_by_requirements"] = tier["band"]
    payload["grade_tier_full_by_requirements"] = tier["full_label"]
    payload["review_tier_max_score"] = display_max
    payload.pop("grade_review_mismatch", None)

    notes = str(payload.get("review_notes") or "").strip()
    if notes:
        if _is_tier_only_excerpt(notes):
            payload["review_notes"] = canonical_tier_review_line(tier, total)
        else:
            payload["review_notes"] = harmonize_review_tier_text(notes, tier, total)
    elif tier.get("label"):
        payload["review_notes"] = canonical_tier_review_line(tier, total)

    grade = str(payload.get("grade") or "").strip()
    if grade:
        payload["grade"] = harmonize_review_tier_text(grade, tier, total)

    summary = payload.get("综合评分")
    if isinstance(summary, dict):
        for key in ("档次", "等第", "grade", "总体评价"):
            val = summary.get(key)
            if isinstance(val, str) and val.strip():
                summary[key] = harmonize_review_tier_text(val, tier, total)

    basis = payload.get("scoring_basis")
    if isinstance(basis, dict):
        review_line = str(payload.get("review_notes") or "").strip()
        if review_line:
            basis["steps_summary"] = review_line
        else:
            steps = basis.get("steps_summary")
            if isinstance(steps, str) and steps.strip():
                basis["steps_summary"] = harmonize_review_tier_text(steps, tier, total)

    recompute_score_confidence_range(payload)


def _status_word(word_ratio: float, char_count: int, word_min: int, word_max: int) -> Status:
    if char_count <= 0:
        return "fail"
    if word_ratio < 0.3:
        return "fail"
    if word_ratio < 0.85:
        return "warn"
    if word_max > 0 and char_count > int(word_max * 1.15):
        return "warn"
    return "ok"


def build_requirement_scoring_summary(
    prompt: str,
    *,
    max_score: float,
    word_min: int,
    word_max: int,
    essay_char_count: int,
    word_ratio: float,
    total_score: float,
    dimension_sum: float = 0.0,
    dimension_max: float = 0.0,
    has_user_material: bool,
    display_reference_only: bool = False,
) -> dict[str, Any]:
    parsed = parse_requirements_from_prompt(prompt)
    declared = parsed.get("declared_max_score")
    use_max = float(declared if declared is not None else max_score)

    req_word_min = int(parsed["word_min"] or word_min)
    req_word_max = int(parsed["word_max"] or word_max)

    dim_sum = float(dimension_sum)
    dim_max = float(dimension_max)

    rows: list[dict[str, Any]] = []

    rows.append(
        {
            "key": "max_score",
            "label": "题目分值",
            "required": f"满分 {int(use_max)} 分"
            + (f"（作答要求写明 {declared} 分）" if declared and int(declared) != int(max_score) else ""),
            "actual": "—" if display_reference_only else f"{total_score:g} / {int(use_max)} 分",
            "status": "info" if display_reference_only else "ok",
        }
    )

    rows.append(
        {
            "key": "word_count",
            "label": "字数要求",
            "required": f"{req_word_min}～{req_word_max} 字（申论正文，非空白字符均计）",
            "actual": f"{essay_char_count} 字（约 {int(word_ratio * 100)}% 下限）",
            "status": _status_word(word_ratio, essay_char_count, req_word_min, req_word_max),
        }
    )

    if parsed.get("requires_use_material") or has_user_material:
        rows.append(
            {
                "key": "material",
                "label": "给定材料",
                "required": "需参考/结合材料" if parsed.get("requires_use_material") else "可选参考背景",
                "actual": "已提交材料" if has_user_material else "未填写材料",
                "status": "ok" if has_user_material else ("warn" if parsed.get("requires_use_material") else "info"),
            }
        )

    if parsed.get("requires_self_title"):
        rows.append(
            {
                "key": "self_title",
                "label": "自拟标题",
                "required": "须自拟标题",
                "actual": "见「主要问题」是否含立意/标题类提示",
                "status": "info",
            }
        )

    if dim_max > 0 or dim_sum > 0:
        rows.append(
            {
                "key": "dimensions",
                "label": "维度得分合计",
                "required": f"立意/结构/论证/语言等维度满分之和 {dim_max:g} 分",
                "actual": "—"
                if display_reference_only
                else f"维度加总 {dim_sum:g} 分（报告总分 {total_score:g} 分）",
                "status": "info"
                if display_reference_only
                else ("ok" if abs(dim_sum - total_score) <= 2.5 else "warn"),
            }
        )

    return {
        "parsed": parsed,
        "rows": rows,
        "prompt_source": "user_submission",
    }
