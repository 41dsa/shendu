#!/usr/bin/env python3
"""REP-05：修改建议须绑定 trait_id + 可操作文案。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.orchestrator import run_scoring_engine
from app.services.scoring_engine.trait_report_builder import build_structured_suggestions


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="rep05",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="rep05",
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
    )


def main() -> None:
    essay = ("基层治理现代化\n\n" + "完善治理体系，推进基层治理现代化。" * 28).strip()
    engine = run_scoring_engine(_ctx(), essay)
    assert not isinstance(engine, dict)
    spine = build_structured_suggestions(engine.trait_diagnostics)
    assert len(spine) >= 1
    for row in spine:
        assert str(row.get("trait_id") or "").startswith("T")
        assert len(str(row.get("text") or "")) >= 8

    payload = merge_engine_with_llm_payload(
        engine,
        {"suggestions": [{"trait_id": "T3", "text": "T3 补充分论点与层次"}]},
        max_score=40.0,
        grading_ctx=_ctx(),
    )
    for row in payload.get("structured_suggestions") or []:
        assert str(row.get("trait_id") or "").startswith("T")
        assert row.get("text")
    print("verify_rep05_structured_suggestions: OK")


if __name__ == "__main__":
    main()
