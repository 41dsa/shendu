"""L2 共识融合与置信度公式。"""

from __future__ import annotations

from typing import Any

CONSENSUS_THRESHOLD = {
    "main": 0.75,
    "sub": 0.67,
    "evidence": 0.5,
    "theme": 0.67,
}


def consensus_ratio(votes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return votes / total


def passes_consensus(point_type: str, votes: int, total: int) -> bool:
    ratio = consensus_ratio(votes, total)
    threshold = CONSENSUS_THRESHOLD.get(point_type, 0.67)
    return ratio >= threshold


def compute_point_confidence(
    *,
    consensus: float,
    evidence_strength: float,
    position_weight: float,
    w1: float = 0.45,
    w2: float = 0.35,
    w3: float = 0.20,
) -> float:
    return round(max(0.0, min(1.0, w1 * consensus + w2 * evidence_strength + w3 * position_weight)), 3)


def evidence_strength_from_source(source_para: list[int], *, in_material: bool) -> float:
    if in_material and source_para:
        return 0.95
    if source_para:
        return 0.8
    if in_material:
        return 0.65
    return 0.45


def position_weight_from_para(para_idx: int, *, total_paras: int) -> float:
    if para_idx <= 0:
        return 0.5
    if para_idx == 1 or (total_paras > 0 and para_idx >= total_paras):
        return 0.85
    return 0.65


def merge_vote_results(votes_by_reviewer: list[dict[str, Any]], *, min_votes: int = 2) -> list[dict[str, Any]]:
    """按 text 归并投票。"""
    buckets: dict[str, dict[str, Any]] = {}
    for batch in votes_by_reviewer:
        for item in batch.get("points") or []:
            text = str(item.get("text") or "").strip()
            if len(text) < 4:
                continue
            key = text[:80]
            bucket = buckets.setdefault(
                key,
                {
                    "text": text,
                    "accept_votes": 0,
                    "total_votes": 0,
                    "keywords": set(),
                    "source_para": set(),
                    "point_type": item.get("point_type") or "sub",
                    "reviewers": [],
                },
            )
            bucket["total_votes"] += 1
            if item.get("accept"):
                bucket["accept_votes"] += 1
            for kw in item.get("keywords") or []:
                bucket["keywords"].add(str(kw))
            for p in item.get("source_para") or []:
                bucket["source_para"].add(int(p))
            bucket["reviewers"].append(item.get("reviewer") or "unknown")

    out: list[dict[str, Any]] = []
    for bucket in buckets.values():
        accept = bucket["accept_votes"]
        total = bucket["total_votes"]
        ptype = str(bucket["point_type"])
        if accept < min_votes and not passes_consensus(ptype, accept, total):
            continue
        out.append(
            {
                "text": bucket["text"],
                "accept_votes": accept,
                "total_votes": total,
                "keywords": sorted(bucket["keywords"]),
                "source_para": sorted(bucket["source_para"]),
                "point_type": ptype,
                "reviewers": bucket["reviewers"],
            }
        )
    return out
