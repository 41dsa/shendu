#!/usr/bin/env python3
"""REP-01：诊断开篇七问字段齐全，LLM 不得改写 Trait 等级。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.orchestrator import run_scoring_engine

SEVEN_KEYS = (
    "q1_task",
    "q2_met",
    "q3_evidence",
    "q4_unmet",
    "q5_loss_sources",
    "q6_disputes",
    "q7_next_steps",
)


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="rep01",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：网格化管理",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="rep01",
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
    )


def main() -> None:
    essay = ("基层治理现代化\n\n" + "完善治理体系，推进基层治理现代化。" * 28).strip()
    engine = run_scoring_engine(_ctx(), essay)
    assert not isinstance(engine, dict)
    before = {r["trait_id"]: r["level"] for r in engine.trait_diagnostics}

    payload = merge_engine_with_llm_payload(
        engine,
        {
            "trait_evidence": [{"trait_id": "T1", "level": "L0"}],
            "diagnostic_polish": {"q7_next_steps": ["润色后的第七问步骤"]},
        },
        max_score=40.0,
        grading_ctx=_ctx(),
    )
    header = payload.get("diagnostic_header") or {}
    for key in SEVEN_KEYS:
        assert key in header, key
    assert header.get("q7_next_steps")
    after = {r["trait_id"]: r["level"] for r in payload.get("trait_diagnostics") or []}
    assert before == after, (before, after)
    print("verify_rep01_diagnostic_seven: OK")


if __name__ == "__main__":
    main()
