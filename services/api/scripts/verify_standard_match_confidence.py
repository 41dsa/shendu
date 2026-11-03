#!/usr/bin/env python3
"""P-02：标准匹配置信度写入引擎结果与报告 payload。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.orchestrator import run_scoring_engine


def main() -> None:
    ctx = EssayGradingContext(
        title="t",
        prompt="写一篇文章",
        reference_material="材料",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="mc",
        question_id="q1",
        standard_version=2,
        standard_review_status="published",
        question_standard={"keywords": ["基层"], "review_status": "published", "version": 2},
    )
    essay = ("基层治理现代化\n\n" + "完善治理体系，推进基层治理现代化。" * 28).strip()
    result = run_scoring_engine(ctx, essay)
    assert not isinstance(result, dict)
    assert result.standard_match_confidence >= 0.85
    assert result.diagnostic_header.get("standard_match_confidence") is not None
    print("verify_standard_match_confidence: OK")


if __name__ == "__main__":
    main()
