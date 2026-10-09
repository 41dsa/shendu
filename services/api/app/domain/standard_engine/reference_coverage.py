"""参考解析 / 范文与 Rubric 覆盖度（P05 辅助 + 规则启发式）。"""

from typing import Any


def _norm_text(text: str) -> str:
    return "".join(text.split())


def _criterion_probe(core: str, min_len: int = 6) -> str:
    core = _norm_text(core)
    if len(core) <= min_len:
        return core
    return core[: min(len(core), 12)]


def heuristic_reference_coverage_ratio(
    rubric: dict[str, Any],
    reference_excerpts: list[str],
) -> float:
    """无 LLM 时：准则 core 是否在参考摘录中出现片段。"""
    criteria = rubric.get("criteria") or []
    if not criteria:
        return 1.0
    if not reference_excerpts:
        return 0.9
    blob = _norm_text("\n".join(reference_excerpts))
    if not blob:
        return 0.9
    covered = 0
    for c in criteria:
        probe = _criterion_probe(str(c.get("core") or ""))
        if not probe:
            covered += 1
            continue
        if probe in blob:
            covered += 1
    return round(covered / len(criteria), 4)


def coverage_ratio_from_p05(
    p05: dict[str, Any],
    *,
    criteria_count: int,
) -> float:
    """由 P05 JSON 估算 coverage_ratio（供 M6 reference_coverage 检查）。"""
    if criteria_count <= 0:
        return 1.0
    questionable = p05.get("questionable_criteria_ids") or []
    gaps = p05.get("coverage_gaps") or []
    if isinstance(p05.get("coverage_ratio"), (int, float)):
        return round(float(p05["coverage_ratio"]), 4)
    base = (criteria_count - len(set(questionable))) / criteria_count
    gap_penalty = min(0.2, 0.04 * len(gaps))
    return round(max(0.0, min(1.0, base - gap_penalty)), 4)
