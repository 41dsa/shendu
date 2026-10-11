"""准则置信度分级（对齐「生产与评测引擎」§7：高/中/低参与评分规则）。"""

from typing import Any, Literal

CriterionUsageBand = Literal["high", "medium", "low"]

# 与方案文档一致：高可直接参与；中降权；低不得作强制扣分依据
HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.70


def criterion_usage_band(confidence: float) -> CriterionUsageBand:
    c = float(confidence)
    if c >= HIGH_THRESHOLD:
        return "high"
    if c >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def enrich_criterion_contract(criterion: dict[str, Any]) -> dict[str, Any]:
    """补全区间分与 usage_band（不破坏已有字段）。"""
    out = dict(criterion)
    mx = float(out.get("max_score") or 0)
    if out.get("score_max") is None and mx > 0:
        out["score_max"] = mx
    if out.get("score_min") is None and mx > 0:
        out["score_min"] = round(mx * 0.5, 2)
    conf = float(out.get("confidence") or 0.0)
    out["usage_band"] = out.get("usage_band") or criterion_usage_band(conf)
    return out


def enrich_rubric_contract(rubric: dict[str, Any]) -> dict[str, Any]:
    out = dict(rubric)
    criteria = [enrich_criterion_contract(c) for c in (out.get("criteria") or [])]
    out["criteria"] = criteria
    rules = dict(out.get("scoring_rules") or {})
    if "score_confidence_declaration" not in rules:
        rules["score_confidence_declaration"] = "medium"
    rules.setdefault(
        "usage_band_policy",
        {
            "high": "full_weight",
            "medium": "reduced_weight",
            "low": "advisory_only_no_mandatory_deduction",
        },
    )
    out["scoring_rules"] = rules
    loss = []
    for lr in out.get("loss_rules") or []:
        if not isinstance(lr, dict):
            continue
        cap = float(lr.get("deduction_cap") or 0)
        if cap <= 0:
            loss.append(lr)
            continue
        dim = str(lr.get("dimension_id") or "")
        linked = [c for c in criteria if str(c.get("dimension_id")) == dim]
        if linked and all(c.get("usage_band") == "low" for c in linked):
            lr = dict(lr)
            lr["advisory_only"] = True
            lr["explanation_template"] = (
                str(lr.get("explanation_template") or "")
                + "（关联准则置信度偏低，仅建议不强制扣分）"
            ).strip()
        loss.append(lr)
    out["loss_rules"] = loss
    return out


def summarize_criterion_tiers(criteria: list[dict[str, Any]]) -> dict[str, Any]:
    tiers: dict[str, list[str]] = {"high": [], "medium": [], "low": []}
    for c in criteria:
        band = str(c.get("usage_band") or criterion_usage_band(float(c.get("confidence") or 0)))
        cid = str(c.get("id") or "")
        if band in tiers and cid:
            tiers[band].append(cid)
    return {
        "high_count": len(tiers["high"]),
        "medium_count": len(tiers["medium"]),
        "low_count": len(tiers["low"]),
        "by_band": tiers,
    }
