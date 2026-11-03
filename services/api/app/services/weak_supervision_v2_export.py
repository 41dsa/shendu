"""V2-WS：弱监督训练包（标签 + 成对比较边 + 反例模板）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.anchor_bradley_terry import pair_compare_edges_for_question
from app.services.weak_supervision_factory import COUNTEREXAMPLE_TEMPLATES, export_weak_labels


def export_weak_supervision_bundle(
    db: Session,
    *,
    question_id: str | None = None,
    label_limit: int = 5000,
) -> dict[str, Any]:
    labels = export_weak_labels(db, limit=label_limit)
    if question_id:
        labels = [x for x in labels if x.get("question_id") == question_id]
    edges_raw = pair_compare_edges_for_question(db, question_id) if question_id else []
    pair_edges = [
        {"winner_id": w, "loser_id": l, "trait_id": tid}
        for w, l, tid in edges_raw
    ]
    return {
        "schema_version": "weak-supervision-v2",
        "question_id": question_id,
        "weak_labels": labels,
        "pair_compare_edges": pair_edges,
        "counterexample_templates": list(COUNTEREXAMPLE_TEMPLATES),
        "label_count": len(labels),
        "pair_edge_count": len(pair_edges),
    }
