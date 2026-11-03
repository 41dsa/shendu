"""V2-ANCHOR：成对比较 → Bradley-Terry 强度估计（锚/作文相对排序）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import TraitPairCompareStatus, TraitPairCompareTask


def bradley_terry_strengths(
    edges: list[tuple[str, str, str]],
    *,
    iterations: int = 25,
) -> dict[str, float]:
    """
    edges: (winner_id, loser_id, trait_id) — winner 优于 loser。
    返回各 id 的 BT 强度（和为 1）。
    """
    players: set[str] = set()
    wins: dict[str, dict[str, int]] = {}
    for w, l, _ in edges:
        players.add(w)
        players.add(l)
        wins.setdefault(w, {})
        wins[w][l] = wins[w].get(l, 0) + 1
    if not players:
        return {}
    strength = {p: 1.0 / len(players) for p in players}
    for _ in range(max(1, iterations)):
        next_s: dict[str, float] = {}
        for p in players:
            denom = 0.0
            for q in players:
                if p == q:
                    continue
                w_pq = wins.get(p, {}).get(q, 0)
                w_qp = wins.get(q, {}).get(p, 0)
                n_pq = w_pq + w_qp
                if n_pq <= 0:
                    continue
                denom += n_pq / max(strength[p] + strength[q], 1e-9)
            win_total = sum(wins.get(p, {}).values())
            next_s[p] = win_total / denom if denom > 0 else strength[p]
        total = sum(next_s.values()) or 1.0
        strength = {k: v / total for k, v in next_s.items()}
    return strength


def pair_compare_edges_for_question(db: Session, question_id: str) -> list[tuple[str, str, str]]:
    rows = (
        db.query(TraitPairCompareTask)
        .filter(
            TraitPairCompareTask.question_id == question_id,
            TraitPairCompareTask.status == TraitPairCompareStatus.completed,
        )
        .all()
    )
    edges: list[tuple[str, str, str]] = []
    for row in rows:
        result = dict(row.result or {})
        pref = str(result.get("preferred_submission_id") or "")
        tid = str(result.get("trait_id") or row.trait_id or "")
        if not pref:
            continue
        other = row.submission_b_id if pref == row.submission_a_id else row.submission_a_id
        edges.append((pref, other, tid))
    return edges


def anchor_calibration_summary(db: Session, question_id: str) -> dict[str, Any]:
    edges = pair_compare_edges_for_question(db, question_id)
    by_trait: dict[str, list[tuple[str, str, str]]] = {}
    for e in edges:
        by_trait.setdefault(e[2] or "all", []).append(e)
    trait_scores: dict[str, dict[str, float]] = {}
    for tid, trait_edges in by_trait.items():
        trait_scores[tid] = bradley_terry_strengths(trait_edges)
    overall = bradley_terry_strengths(edges) if edges else {}
    ranked = sorted(overall.items(), key=lambda x: x[1], reverse=True)
    return {
        "question_id": question_id,
        "pair_count": len(edges),
        "overall_strengths": overall,
        "ranked_submission_ids": [sid for sid, _ in ranked],
        "by_trait": trait_scores,
    }
