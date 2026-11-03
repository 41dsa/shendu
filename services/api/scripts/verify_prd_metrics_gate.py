"""§7.5 阶段性指标门禁（V1：可自动化部分）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.orchestrator import run_scoring_engine


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="metrics-gate",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="metrics-g",
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
        rubric_criteria=[],
        anchor_count=0,
    )


def main() -> None:
    import verify_evidence_grounding
    import verify_hard_rules_suite
    import verify_trait_stability

    verify_evidence_grounding.main()
    verify_hard_rules_suite.main()
    verify_trait_stability.main()

    para = "推进基层治理现代化，完善治理体系、提升治理能力。"
    essay = "推进基层治理现代化\n\n" + "\n\n".join([f"第{i}段：{para}" for i in range(1, 25)])
    ctx = _ctx()
    r1 = run_scoring_engine(ctx, essay)
    r2 = run_scoring_engine(ctx, essay)
    assert not isinstance(r1, dict) and not isinstance(r2, dict)
    lv1 = [d.get("level") for d in r1.trait_diagnostics]
    lv2 = [d.get("level") for d in r2.trait_diagnostics]
    assert lv1 == lv2, (lv1, lv2)

    print("verify_prd_metrics_gate: ok")


if __name__ == "__main__":
    main()
