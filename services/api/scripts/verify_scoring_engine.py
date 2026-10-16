"""分层评分引擎冒烟：闸门、级别、确定性评分、校准、报告适配。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.models.entities import Question, QuestionType
from app.services.essay_context import EssayGradingContext
from app.domain.scoring_engine.types import ScoringEngineResult, ScoringTier
from app.services.grading_helpers import normalize_llm_report_payload
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.orchestrator import run_scoring_engine


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
    enforced = run_scoring_engine(_ctx(exam_level="enforcement"), essay)
    assert not isinstance(enforced, dict)
    assert enforced.exam_level == "enforcement"
    assert enforced.level_inferred is False
    assert 0 <= result.total_score <= 40
    assert result.dimension_rows
    assert result.tier.tier_id
    assert result.evidence_chain or result.point_hits
    tier = ScoringTier("t4", "四类文", 0, 15)
    engine_zero = ScoringEngineResult(
        exam_level="municipal",
        level_inferred=True,
        level_config_version="1.0.0",
        point_pool_version="1.0.0",
        total_score=0.0,
        max_score=40.0,
        tier=tier,
        dimension_rows=[],
        point_hits=[],
        penalties={},
        confidence=0.6,
        level_specific_feedback="",
        evidence_chain=[],
        engine_traces=[],
        deliberation_triggered=False,
        deliberation_note="",
    )
    llm_payload = normalize_llm_report_payload(
        {"total_score": 0, "综合评分": {"总分": "31.5 / 40"}},
    )
    merged = merge_engine_with_llm_payload(
        engine_zero,
        llm_payload,
        max_llm_delta=4.0,
        max_score=40.0,
    )
    assert merged["total_score"] == 31.5, merged
    assert merged.get("engine_total_discarded") is True

    from dataclasses import replace

    engine_low = replace(engine_zero, total_score=3.3)
    llm_mid = normalize_llm_report_payload(
        {
            "total_score": 31.0,
            "scoring_points": [
                {"label": "立意与观点", "earned": 7.8, "max": 10, "hit": "partial"},
                {"label": "结构与层次", "earned": 7.5, "max": 10, "hit": "partial"},
                {"label": "论证与素材", "earned": 7.6, "max": 10, "hit": "partial"},
                {"label": "语言表达", "earned": 8.1, "max": 10, "hit": "partial"},
            ],
            "review_notes": "因此止步二类中段，难以进入一类。",
        },
    )
    merged2 = merge_engine_with_llm_payload(engine_low, llm_mid, max_llm_delta=4.0, max_score=40.0)
    assert merged2["total_score"] == 31.0, merged2
    assert merged2.get("engine_total_discarded") is True

    print("verify_scoring_engine: ok")


if __name__ == "__main__":
    main()
