"""Phase 2：Evidence 引擎 grounding 与子串校验冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.domain.scoring_engine.evidence_engine import (
    apply_llm_evidence_to_result,
    extract_rule_evidence,
    ground_quotes,
    quote_is_substring,
)
from app.domain.scoring_engine.essay_signals import analyze_essay_signals
from app.domain.scoring_engine.hard_rules import run_hard_rules
from app.domain.scoring_engine.question_standard_card import build_question_standard_card
from app.services.scoring_engine.orchestrator import run_scoring_engine


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="evidence-test",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="evidence-t",
        standard_version=1,
        standard_review_status="published",
        question_standard={
            "keywords": ["基层治理"],
            "proposition_task": "论证",
            "review_status": "published",
        },
        rubric_criteria=[],
    )


def main() -> None:
    essay = "推进基层治理现代化\n\n" + "完善治理体系，提升治理能力。" * 20
    assert quote_is_substring(essay, "推进基层治理现代化")
    kept, rejected = ground_quotes(essay, ["推进基层治理现代化", "完全虚构的句子不存在"])
    assert len(kept) == 1 and len(rejected) == 1

    ctx = _ctx()
    standard = build_question_standard_card(ctx)
    signals = analyze_essay_signals(essay, standard)
    hard = run_hard_rules(essay, word_min=800, word_max=1200, reference_material=ctx.reference_material or "", main_point_hit=signals.main_thesis_signal)
    base = extract_rule_evidence(essay, signals, hard, standard)
    assert base.overall_grounding_rate >= 0.9
    merged = apply_llm_evidence_to_result(
        essay,
        base,
        {
            "T1": {
                "evidence_positive": ["推进基层治理现代化", "幻觉摘录不应保留"],
                "evidence_negative": [],
                "evidence_missing": [],
            }
        },
    )
    t1 = merged.by_trait["T1"]
    assert "推进基层治理现代化" in t1.positive
    assert not any("幻觉" in q for q in t1.positive)
    assert merged.overall_grounding_rate <= 1.0
    pos_spans = [s for s in t1.spans if s.grounded]
    assert pos_spans and pos_spans[0].start is not None and pos_spans[0].end is not None

    result = run_scoring_engine(ctx, essay)
    assert not isinstance(result, dict)
    trace_layers = [t.layer for t in result.engine_traces]
    assert "evidence_engine" in trace_layers
    for row in result.trait_diagnostics:
        rate = row.get("evidence_grounding_rate")
        assert rate is None or 0.0 <= float(rate) <= 1.0

    print("verify_evidence_grounding: ok")


if __name__ == "__main__":
    main()
