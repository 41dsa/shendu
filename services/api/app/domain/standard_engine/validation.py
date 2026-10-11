"""标准验证器（M6 纯规则部分）。"""

from typing import Any

from app.domain.standard_engine.criterion_confidence import (
    enrich_rubric_contract,
    summarize_criterion_tiers,
)


def _check_score_sum(rubric: dict[str, Any]) -> dict[str, Any]:
    total = int(rubric.get("total_score") or 0)
    dimensions = rubric.get("dimensions") or []
    actual = sum(int(d.get("max_score") or 0) for d in dimensions)
    passed = total > 0 and actual == total
    return {
        "id": "score_sum",
        "passed": passed,
        "expected": total,
        "actual": actual,
        "detail": "维度满分之和须等于题目总分" if not passed else "ok",
    }


def _check_dimension_consistency(rubric: dict[str, Any]) -> dict[str, Any]:
    """论证维准则不应仅描述字数。"""
    criteria = {c["id"]: c for c in (rubric.get("criteria") or []) if c.get("id")}
    bad: list[str] = []
    for dim in rubric.get("dimensions") or []:
        label = str(dim.get("label") or "")
        if "论证" not in label and "素材" not in label:
            continue
        for cid in dim.get("criteria") or []:
            crit = criteria.get(cid)
            if not crit:
                continue
            core = str(crit.get("core") or "")
            if "字数" in core and len(core) < 12:
                bad.append(cid)
    passed = len(bad) == 0
    return {
        "id": "dimension_consistency",
        "passed": passed,
        "questionable_criteria_ids": bad,
        "detail": "论证维含纯字数准则" if bad else "ok",
    }


def _check_duplicate_criteria(rubric: dict[str, Any], max_duplicate_rate: float = 0.05) -> dict[str, Any]:
    """同维 core 文本完全重复视为重复项。"""
    by_dim: dict[str, list[str]] = {}
    criteria = rubric.get("criteria") or []
    for c in criteria:
        dim = str(c.get("dimension_id") or "")
        core = str(c.get("core") or "").strip()
        by_dim.setdefault(dim, []).append(core)
    duplicates = 0
    total = 0
    for cores in by_dim.values():
        total += len(cores)
        duplicates += len(cores) - len(set(cores))
    rate = (duplicates / total) if total else 0.0
    passed = rate <= max_duplicate_rate
    return {
        "id": "duplicate_criteria",
        "passed": passed,
        "duplicate_rate": round(rate, 4),
        "detail": f"重复率 {rate:.2%}",
    }


def _check_prompt_traceability(
    question_standard: dict[str, Any],
    rubric: dict[str, Any],
    prompt_text: str,
) -> dict[str, Any]:
    """简化：focus_points 非空且题干长度合理即通过；准则须含 dimension_id。"""
    focus = question_standard.get("focus_points") or []
    criteria = rubric.get("criteria") or []
    missing_dim = [c.get("id") for c in criteria if not c.get("dimension_id")]
    passed = len(prompt_text.strip()) >= 20 and len(focus) >= 1 and not missing_dim
    return {
        "id": "prompt_traceability",
        "passed": passed,
        "detail": "focus_points 或准则 dimension_id 不足" if not passed else "ok",
    }


def _check_criterion_intervals(rubric: dict[str, Any]) -> dict[str, Any]:
    bad: list[str] = []
    for c in rubric.get("criteria") or []:
        cid = str(c.get("id") or "")
        mn = c.get("score_min")
        mx = c.get("score_max")
        cap = float(c.get("max_score") or 0)
        if cap <= 0 or mn is None or mx is None:
            continue
        if float(mn) > float(mx) or float(mx) > cap + 0.01:
            bad.append(cid)
    return {
        "id": "criterion_score_intervals",
        "passed": len(bad) == 0,
        "invalid_criterion_ids": bad,
        "detail": "准则分区间须满足 score_min ≤ score_max ≤ max_score" if bad else "ok",
    }


def run_standard_validators(
    *,
    question_standard: dict[str, Any],
    rubric: dict[str, Any],
    prompt_text: str,
    reference_coverage_ratio: float | None = None,
) -> dict[str, Any]:
    rubric = enrich_rubric_contract(rubric)
    tier_summary = summarize_criterion_tiers(rubric.get("criteria") or [])
    checks = [
        _check_prompt_traceability(question_standard, rubric, prompt_text),
        _check_dimension_consistency(rubric),
        _check_duplicate_criteria(rubric),
        _check_score_sum(rubric),
    ]
    ref_ratio = reference_coverage_ratio if reference_coverage_ratio is not None else 1.0
    checks.insert(
        1,
        {
            "id": "reference_coverage",
            "passed": ref_ratio >= 0.85,
            "coverage_ratio": ref_ratio,
            "detail": "参考答案/解析覆盖" if ref_ratio >= 0.85 else "覆盖不足",
        },
    )
    checks.append(_check_criterion_intervals(rubric))
    overall = all(c.get("passed") for c in checks)
    return {
        "checks": checks,
        "overall_passed": overall,
        "blocking_issues": [c["id"] for c in checks if not c.get("passed")],
        "criterion_confidence_tiers": tier_summary,
        "enriched_rubric": rubric,
    }
