#!/usr/bin/env python3
"""P-05：金标作文 Trait 等级回归（有样本时 Δ 档位稳定）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, DEMO_QUESTION_ID
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.models.entities import GoldSample
from app.services.scoring_engine.orchestrator import run_scoring_engine


def _ctx_for_question(qid: str) -> EssayGradingContext:
    return EssayGradingContext(
        title="gold",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key=f"gold-{qid}",
        question_id=qid,
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
    )


def main() -> None:
    db = SessionLocal()
    try:
        samples = (
            db.query(GoldSample)
            .filter(GoldSample.question_id == DEMO_QUESTION_ID)
            .limit(5)
            .all()
        )
        if not samples:
            print("verify_trait_gold_regression: SKIP (no gold samples)")
            return
        ctx = _ctx_for_question(DEMO_QUESTION_ID)
        checked = 0
        for sample in samples:
            content = (sample.reference_answer or "").strip()
            if len(content) < 200:
                continue
            r1 = run_scoring_engine(ctx, content)
            r2 = run_scoring_engine(ctx, content)
            assert not isinstance(r1, dict) and not isinstance(r2, dict)
            lv1 = [d.get("level") for d in r1.trait_diagnostics]
            lv2 = [d.get("level") for d in r2.trait_diagnostics]
            assert lv1 == lv2, sample.id
            checked += 1
        if checked == 0:
            print("verify_trait_gold_regression: SKIP (no usable gold text)")
            return
        print(f"verify_trait_gold_regression: OK ({checked} samples)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
