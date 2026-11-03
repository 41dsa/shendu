"""PRD V1 Trait 评分引擎冒烟：硬规则、八大 Trait、区间与置信度。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.orchestrator import run_scoring_engine


def _ctx(**kwargs) -> EssayGradingContext:
    base = dict(
        title="2024国考副省级",
        prompt="围绕基层治理写一篇文章，1000字左右，满分40分",
        reference_material="材料：推进基层治理现代化，完善网格化管理。",
        material_structured={"exam": "国考副省级", "year": 2024, "word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="trait-t",
        standard_version=1,
        standard_review_status="published",
        question_standard={
            "keywords": ["基层治理"],
            "proposition_task": "论证",
            "review_status": "published",
        },
        rubric_criteria=[
            {
                "id": "RC1",
                "dimension_id": "D01",
                "core": "基层治理",
                "acceptable_expressions": ["基层治理现代化", "治理体系"],
                "max_score": 10,
                "confidence": 0.9,
            }
        ],
    )
    base.update(kwargs)
    return EssayGradingContext(**base)


def main() -> None:
    para = "推进基层治理现代化，要完善治理体系、提升治理能力，以数字化赋能网格化管理。"
    essay = "推进基层治理现代化\n\n" + "\n\n".join([f"第{i}段：{para}" for i in range(1, 25)])
    result = run_scoring_engine(_ctx(), essay)
    assert not isinstance(result, dict), result
    assert len(result.trait_diagnostics) == 8, len(result.trait_diagnostics)
    assert result.ability_level
    assert result.score_interval and result.score_interval[0] <= result.score_interval[1]
    assert result.system_center_score is not None
    c_tier = [d for d in result.trait_diagnostics if d.get("standard_tier") == "C"]
    assert len(c_tier) == 3
    assert all(d.get("participates_in_score") is False for d in c_tier)
    b_scored = [d for d in result.trait_diagnostics if d.get("participates_in_score")]
    assert len(b_scored) == 5
    for d in result.trait_diagnostics:
        assert "evidence_positive" in d
        assert d.get("level") in ("L0", "L1", "L2", "L3", "L4")
    print("verify_trait_scoring_engine: ok")


if __name__ == "__main__":
    main()
