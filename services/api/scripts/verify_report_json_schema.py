"""REP：Trait V1 报告 JSON 必填字段校验。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.orchestrator import run_scoring_engine
from app.services.scoring_engine.trait_report_builder import REPORT_SCHEMA_VERSION

REQUIRED_TOP = (
    "report_schema",
    "trait_diagnostics",
    "diagnostic_header",
    "score_disclaimer",
    "non_official_notice",
    "scoring_engine",
)


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="schema-test",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="schema-t",
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
    payload = merge_engine_with_llm_payload(engine, {"issues": [], "suggestions": []}, max_score=40.0, grading_ctx=_ctx())
    for key in REQUIRED_TOP:
        assert key in payload, key
    assert payload["report_schema"] == REPORT_SCHEMA_VERSION
    header = payload["diagnostic_header"]
    for q in ("q1_task", "q5_loss_sources", "q7_next_steps"):
        assert q in header, q
    eng = payload["scoring_engine"]
    assert eng.get("engine") == "diagnostic_trait_v1"
    print("verify_report_json_schema: ok")


if __name__ == "__main__":
    main()
