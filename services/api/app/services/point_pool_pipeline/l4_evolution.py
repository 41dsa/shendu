"""L4 点池自进化：基于评分命中日志的遗漏/冗余/权重建议。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def audit_point_pool_from_logs(
    *,
    point_ids: list[str],
    hit_logs: list[dict[str, Any]],
) -> dict[str, Any]:
    """按级别聚合命中共现，输出运营可读的迭代建议。"""
    co_occur: dict[tuple[str, str], int] = defaultdict(int)
    hit_counts: dict[str, int] = defaultdict(int)
    miss_counts: dict[str, int] = defaultdict(int)
    high_score_miss: dict[str, int] = defaultdict(int)

    for row in hit_logs:
        pid = str(row.get("point_id") or "")
        status = str(row.get("status") or "")
        total_score = float(row.get("total_score") or 0)
        if not pid:
            continue
        if status in ("hit", "partial", "borderline"):
            hit_counts[pid] += 1
        else:
            miss_counts[pid] += 1
            if total_score >= 28:
                high_score_miss[pid] += 1

    submissions_points: list[set[str]] = []
    by_sub: dict[str, set[str]] = defaultdict(set)
    for row in hit_logs:
        sid = str(row.get("submission_id") or row.get("grading_job_id") or "")
        pid = str(row.get("point_id") or "")
        if sid and pid and str(row.get("status") or "") in ("hit", "partial", "borderline"):
            by_sub[sid].add(pid)
    submissions_points = list(by_sub.values())

    merge_candidates: list[dict[str, Any]] = []
    for i, a in enumerate(point_ids):
        for b in point_ids[i + 1 :]:
            together = sum(1 for s in submissions_points if a in s and b in s)
            either = sum(1 for s in submissions_points if a in s or b in s)
            if either >= 5 and together / either >= 0.92:
                merge_candidates.append({"point_a": a, "point_b": b, "co_rate": round(together / either, 3)})

    add_candidates = [
        {"point_id": pid, "high_score_miss": n}
        for pid, n in high_score_miss.items()
        if n >= 3
    ]

    return {
        "merge_suggestions": merge_candidates[:20],
        "add_suggestions": add_candidates[:20],
        "hit_counts": dict(hit_counts),
        "miss_counts": dict(miss_counts),
        "sample_size": len(submissions_points),
    }
