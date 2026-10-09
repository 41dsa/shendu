"""双路 Rubric 候选一致率（P03 主模型 vs 共识模型）。"""

from typing import Any


def _candidate_keys(candidates: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for c in candidates:
        dim = str(c.get("dimension_id") or "")
        core = "".join(str(c.get("core") or "").split())[:48]
        if dim or core:
            keys.add(f"{dim}::{core}")
    return keys


def rubric_candidates_agreement(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> float:
    """Jaccard 相似度，用于 confidence 的 model_agreement 分量。"""
    a = _candidate_keys(primary)
    b = _candidate_keys(secondary)
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 1.0
    return round(len(a & b) / len(union), 4)
