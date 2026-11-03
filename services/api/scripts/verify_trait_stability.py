#!/usr/bin/env python3
"""§7.5 Trait 稳定性：同题同文多次运行等级一致。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.orchestrator import run_scoring_engine

RUNS = 5


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="trait-stability",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="trait-stab",
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
        rubric_criteria=[],
        anchor_count=0,
    )


def main() -> None:
    para = "推进基层治理现代化，完善治理体系、提升治理能力。"
    essay = "推进基层治理现代化\n\n" + "\n\n".join([f"第{i}段：{para}" for i in range(1, 25)])
    ctx = _ctx()
    levels_per_run: list[list[str | None]] = []
    for _ in range(RUNS):
        result = run_scoring_engine(ctx, essay)
        assert not isinstance(result, dict)
        levels_per_run.append([d.get("level") for d in result.trait_diagnostics])
    first = levels_per_run[0]
    for i, lv in enumerate(levels_per_run[1:], start=2):
        assert lv == first, f"run {i} diverged from run 1: {lv} vs {first}"
    print(f"verify_trait_stability: ok ({RUNS} runs identical)")


if __name__ == "__main__":
    main()
