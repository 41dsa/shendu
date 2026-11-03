#!/usr/bin/env python3
"""DEP-03：批改不依赖点池；标准生产点池为可选遗留。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    from app.config import settings
    from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
    from app.domain.essay_grading_context import EssayGradingContext
    from app.domain.question_type import QuestionType
    from app.services.scoring_engine.orchestrator import run_scoring_engine

    assert settings.point_pool_pipeline_enabled is False
    ctx = EssayGradingContext(
        title="dep03",
        prompt="写一篇文章",
        reference_material="材料",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="dep03",
        point_pools=None,
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层"], "review_status": "published"},
    )
    essay = ("基层治理现代化\n\n" + "完善治理体系，推进基层治理现代化。" * 28).strip()
    result = run_scoring_engine(ctx, essay)
    assert not isinstance(result, dict)
    assert len(result.trait_diagnostics) == 8
    assert not result.point_hits
    print("verify_dep03_point_pool_optional: OK")


if __name__ == "__main__":
    main()
