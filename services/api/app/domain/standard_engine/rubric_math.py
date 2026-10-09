"""Rubric 分值归一：维度之和 = total_score。"""

from typing import Any


def normalize_dimension_scores(dimensions: list[dict[str, Any]], total_score: int) -> list[dict[str, Any]]:
    if not dimensions:
        return dimensions
    dims = [dict(d) for d in dimensions]
    current = sum(int(d.get("max_score") or 0) for d in dims)
    if current == total_score:
        return dims
    if current <= 0:
        per = total_score // len(dims)
        rem = total_score - per * len(dims)
        for i, d in enumerate(dims):
            d["max_score"] = per + (rem if i == 0 else 0)
        return dims
    scale = total_score / current
    scaled = [max(1, int(round(int(d.get("max_score") or 0) * scale))) for d in dims]
    diff = total_score - sum(scaled)
    scaled[0] += diff
    for d, s in zip(dims, scaled, strict=True):
        d["max_score"] = s
    return dims
