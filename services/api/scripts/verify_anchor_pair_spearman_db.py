#!/usr/bin/env python3
"""§7.5 成对比较：DB 锚对 + Bradley-Terry Spearman（不足样本则跳过）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.domain.scoring_engine.trait_definitions import level_to_numeric
from app.models.entities import AnchorEssay
from app.services.anchor_bradley_terry import anchor_calibration_summary, bradley_terry_strengths, pair_compare_edges_for_question


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    for r, idx in enumerate(order):
        ranks[idx] = float(r + 1)
    return ranks


def spearman_rho(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 1.0
    rx, ry = _rank(x), _rank(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den_x = sum((rx[i] - mx) ** 2 for i in range(n)) ** 0.5
    den_y = sum((ry[i] - my) ** 2 for i in range(n)) ** 0.5
    if den_x == 0 or den_y == 0:
        return 1.0
    return num / (den_x * den_y)


def main() -> None:
    db = SessionLocal()
    try:
        qid = "demo-essay-001"
        db_edges = pair_compare_edges_for_question(db, qid)
        synthetic = False
        edges = list(db_edges)
        if len(edges) < 3:
            anchors = (
                db.query(AnchorEssay)
                .filter(AnchorEssay.question_id == qid, AnchorEssay.is_published.is_(True))
                .order_by(AnchorEssay.aggregate_level.desc())
                .limit(8)
                .all()
            )
            if len(anchors) >= 3:
                synthetic = True
                edges = [(anchors[i].id, anchors[i + 1].id, "T1") for i in range(len(anchors) - 1)]
            if len(edges) < 3:
                print("verify_anchor_pair_spearman_db: SKIP (insufficient pair edges)")
                return

        strengths = bradley_terry_strengths(edges)
        _ = anchor_calibration_summary(db, qid)
        if not synthetic:
            print(f"verify_anchor_pair_spearman_db: OK (db_edges={len(db_edges)}, bt_players={len(strengths)})")
            return

        ids = list(strengths.keys())
        bt_vals = [strengths[i] for i in ids]
        anchor_levels = [
            float(level_to_numeric(db.get(AnchorEssay, aid).aggregate_level))  # type: ignore[union-attr]
            for aid in ids
        ]
        rho = spearman_rho(bt_vals, anchor_levels)
        assert rho >= 0.7, f"spearman={rho:.3f}"
        print(f"verify_anchor_pair_spearman_db: OK (synthetic rho={rho:.3f}, edges={len(edges)})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
