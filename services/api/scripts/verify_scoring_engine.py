"""PRD V1 Trait 诊断评分引擎冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dataclasses import replace

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.domain.scoring_engine.types import ScoringEngineResult, ScoringTier
from app.services.grading_helpers import normalize_llm_report_payload
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.orchestrator import run_scoring_engine

_TRAIT_ROW = {
    "trait_id": "T1",
    "name": "审题与任务完成",
    "standard_tier": "B",
    "level": "L3",
    "participates_in_score": True,
    "confidence": 0.8,
    "evidence_positive": ["推进基层治理现代化"],
    "evidence_negative": [],
    "evidence_missing": [],
    "conclusion": "L3",
    "dispute_hint": "",
}


def _ctx(**kwargs) -> EssayGradingContext:
    base = dict(
        title="2024国考副省级",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"exam": "国考副省级", "year": 2024, "word_min": 200, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="t",
        standard_version=1,
        question_standard={"proposition_task": "论证观点", "keywords": ["基层治理", "治理体系"]},
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
    short = run_scoring_engine(_ctx(), "太短")
    assert isinstance(short, dict) and short.get("short_circuit_reason"), short

    para = "推进基层治理现代化，要完善治理体系、提升治理能力，以数字化赋能网格化管理。"
    essay = "推进基层治理现代化\n\n" + "\n\n".join([f"第{i}段：{para}" for i in range(1, 25)])
    result = run_scoring_engine(_ctx(), essay)
    assert not isinstance(result, dict)
    assert result.exam_level == "provincial"
    assert len(result.trait_diagnostics) == 8
    assert result.ability_level
    assert result.evidence_chain
    assert not result.point_hits

    tier = ScoringTier("t4", "四类文", 0, 15)
    engine_trait = ScoringEngineResult(
        exam_level="municipal",
        level_inferred=True,
        level_config_version="1.0.0",
        point_pool_version="essay-trait-v1.0.0",
        total_score=27.0,
        max_score=40.0,
        tier=tier,
        dimension_rows=[],
        point_hits=[],
        penalties={},
        confidence=0.78,
        level_specific_feedback="",
        evidence_chain=[],
        engine_traces=[],
        trait_diagnostics=[_TRAIT_ROW],
        system_center_score=27.0,
        score_interval=(25.0, 29.0),
        suppress_absolute_score=False,
    )
    llm_mid = normalize_llm_report_payload({"total_score": 31.0})
    merged = merge_engine_with_llm_payload(engine_trait, llm_mid, max_score=40.0)
    assert merged["total_score"] == 27.0, merged
    assert merged.get("llm_total_discarded") is True
    assert merged.get("trait_score_spine") is True

    engine_suppressed = replace(engine_trait, suppress_absolute_score=True, total_score=0.0)
    merged2 = merge_engine_with_llm_payload(engine_suppressed, llm_mid, max_score=40.0)
    assert merged2["total_score"] == 0.0
    assert merged2.get("display_mode") == "reference_only"

    engine_interval = replace(
        engine_trait,
        score_display_mode="interval",
        score_uncalibrated=True,
        total_score=0.0,
    )
    merged3 = merge_engine_with_llm_payload(engine_interval, llm_mid, max_score=40.0)
    assert merged3["total_score"] == 0.0
    assert merged3.get("display_mode") == "interval_only"

    print("verify_scoring_engine: ok")


if __name__ == "__main__":
    main()
