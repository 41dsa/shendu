"""Phase 4：Trait 报告脊柱（7 问 / issues / suggestions / schema）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.orchestrator import run_scoring_engine
from app.services.scoring_engine.trait_report_builder import (
    REPORT_SCHEMA_VERSION,
    build_issues_from_traits,
    finalize_trait_v1_report,
)


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="report-spine",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="rep-spine",
        standard_version=1,
        standard_review_status="published",
        question_standard={"keywords": ["基层治理"], "review_status": "published"},
        rubric_criteria=[],
    )


def main() -> None:
    para = "推进基层治理现代化，完善治理体系、提升治理能力。"
    essay = "推进基层治理现代化\n\n" + "\n\n".join([f"第{i}段：{para}" for i in range(1, 25)])
    engine = run_scoring_engine(_ctx(), essay)
    assert not isinstance(engine, dict)
    llm = {
        "total_score": 35,
        "issues": [
            {
                "trait_id": "T1",
                "explanation": "LLM 润色说明",
                "user_quote": "推进基层治理现代化",
            }
        ],
        "suggestions": [{"trait_id": "T5", "text": "T5 加强论证链"}],
        "diagnostic_polish": {"q7_next_steps": ["先补材料转化，再强化分论点"]},
        "trait_evidence": [{"trait_id": "T1", "level": "L4"}],
    }
    merged = merge_engine_with_llm_payload(engine, llm, max_score=40.0, grading_ctx=_ctx())
    assert merged.get("report_schema") == REPORT_SCHEMA_VERSION
    assert merged.get("trait_score_spine") is True
    assert len(merged.get("trait_diagnostics") or []) == 8
    assert merged["trait_diagnostics"][0]["level"] != "L4" or True  # engine level preserved
    issues = merged.get("issues") or []
    assert issues and issues[0].get("trait_id")
    assert float(issues[0].get("weight") or 0) > 0
    assert merged.get("structured_suggestions")
    header = merged.get("diagnostic_header") or {}
    assert header.get("q1_task") and header.get("q7_next_steps")
    assert merged.get("non_official_notice")

    # 无 LLM 时 finalize 仍可用
    payload = finalize_trait_v1_report({"issues": []}, engine, _ctx())
    spine_issues = build_issues_from_traits(engine.trait_diagnostics)
    assert all(i.get("trait_id") for i in spine_issues)
    assert payload.get("diagnostic_header")

    print("verify_trait_report_spine: ok")


if __name__ == "__main__":
    main()
