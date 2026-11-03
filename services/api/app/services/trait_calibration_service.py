"""V3-CAL：金标 / 锚多评 QWK 与门禁报告。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.calibration_metrics import (
    CalibrationGateResult,
    evaluate_calibration_gate,
    quadratic_weighted_kappa,
)
from app.domain.scoring_engine.trait_definitions import level_to_numeric
from app.models.entities import AnchorTraitReview, GoldRun, GoldSample


def _score_to_ordinal(score: float, *, max_score: float = 40.0, bins: int = 5) -> int:
    s = max(0.0, min(max_score, float(score)))
    return min(bins - 1, int(s / max_score * bins))


def gold_regression_calibration(db: Session, *, limit: int = 200) -> dict[str, Any]:
    runs = db.query(GoldRun).order_by(GoldRun.created_at.desc()).limit(limit).all()
    y_true: list[int] = []
    y_pred: list[int] = []
    rows_detail: list[dict[str, Any]] = []
    for run in runs:
        if run.ai_score is None or run.expected_mid is None:
            continue
        t = _score_to_ordinal(run.expected_mid)
        p = _score_to_ordinal(run.ai_score)
        y_true.append(t)
        y_pred.append(p)
        sample = db.get(GoldSample, run.gold_sample_id)
        rows_detail.append(
            {
                "gold_sample_id": run.gold_sample_id,
                "question_id": sample.question_id if sample else None,
                "expected_ordinal": t,
                "ai_ordinal": p,
                "abs_delta": run.score_delta,
            }
        )
    min_qwk = float(getattr(settings, "v3_calibration_min_qwk", 0.55))
    min_n = int(getattr(settings, "v3_calibration_min_gold_runs", 5))
    gate: CalibrationGateResult = evaluate_calibration_gate(y_true, y_pred, min_qwk=min_qwk, min_samples=min_n)
    return {
        "source": "gold_regression",
        "pair_count": len(y_true),
        "qwk": gate.qwk,
        "gate_passed": gate.passed,
        "gate_reason": gate.reason,
        "min_qwk": min_qwk,
        "min_samples": min_n,
        "recent": rows_detail[:20],
    }


def anchor_reviewer_calibration(db: Session, *, question_id: str | None = None) -> dict[str, Any]:
    q = db.query(AnchorTraitReview)
    if question_id:
        from app.models.entities import AnchorEssay

        anchor_ids = [
            row[0]
            for row in db.query(AnchorEssay.id).filter(AnchorEssay.question_id == question_id).all()
        ]
        if not anchor_ids:
            return {"source": "anchor_trait_reviews", "pair_count": 0, "qwk": None, "by_trait": {}}
        q = q.filter(AnchorTraitReview.anchor_essay_id.in_(anchor_ids))
    rows = q.all()
    by_key: dict[tuple[str, str], list[int]] = {}
    for r in rows:
        key = (r.anchor_essay_id, r.trait_id)
        by_key.setdefault(key, []).append(level_to_numeric(str(r.level)))
    y_true: list[int] = []
    y_pred: list[int] = []
    icc_rows: list[list[float]] = []
    for levels in by_key.values():
        if len(levels) < 2:
            continue
        icc_rows.append([float(x) for x in levels])
        y_true.append(levels[0])
        y_pred.append(round(sum(levels) / len(levels)))
    min_qwk = float(getattr(settings, "v3_calibration_min_qwk", 0.55))
    min_n = int(getattr(settings, "v3_calibration_min_anchor_pairs", 5))
    gate = evaluate_calibration_gate(
        y_true,
        y_pred,
        min_qwk=min_qwk,
        min_samples=min_n,
        icc_replicates=icc_rows if len(icc_rows) >= 2 else None,
    )
    return {
        "source": "anchor_trait_reviews",
        "question_id": question_id,
        "pair_count": len(y_true),
        "qwk": gate.qwk,
        "icc": gate.icc,
        "gate_passed": gate.passed,
        "gate_reason": gate.reason,
    }


def calibration_dashboard(db: Session) -> dict[str, Any]:
    gold = gold_regression_calibration(db)
    anchor = anchor_reviewer_calibration(db)
    overall_pass = gold.get("gate_passed", True) and anchor.get("gate_passed", True)
    return {
        "schema_version": "v3-cal-v1",
        "overall_gate_passed": overall_pass,
        "gold_regression": gold,
        "anchor_reviews": anchor,
        "note": "V1 不写入 final_calibrated_score；门禁用于发布前自检与 V3 入口。",
    }
