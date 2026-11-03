"""Phase 3：§6.5 多标准视图（strict / loose / dependency）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.domain.scoring_engine.score_display_policy import resolve_score_display_mode
from app.services.scoring_engine.orchestrator import run_scoring_engine


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="multi-view-test",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="msv-t",
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
        rubric_criteria=[],
    )


def main() -> None:
    para = "推进基层治理现代化，完善治理体系、提升治理能力。"
    essay = "推进基层治理现代化\n\n" + "\n\n".join([f"第{i}段：{para}" for i in range(1, 25)])
    result = run_scoring_engine(_ctx(), essay)
    assert not isinstance(result, dict)
    views = result.multi_standard_views
    assert views.get("strict") and views.get("loose") and views.get("dependency")
    assert views.get("labels", {}).get("strict")
    dep_traits = views["dependency"].get("traits") or []
    assert dep_traits and "严格视角" in str(dep_traits[0].get("dispute_hint") or "")
    strict_c = float(views["strict"]["system_center"])
    loose_c = float(views["loose"]["system_center"])
    base_c = float(views["baseline"]["system_center"])
    assert strict_c <= base_c + 0.01
    assert loose_c >= base_c - 0.01
    dep = views["dependency"]
    assert len(dep.get("traits") or []) == 3
    mode = resolve_score_display_mode(
        suppress_absolute_score=False,
        trait_confidence=result.trait_confidence,
        score_uncalibrated=True,
        anchor_count=0,
        diagnostic_only_mode=False,
    )
    assert mode == "interval", mode
    assert result.score_display_mode in ("tier_only", "interval", "center")
    print("verify_multi_standard_views: ok")


if __name__ == "__main__":
    main()
