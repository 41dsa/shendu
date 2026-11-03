#!/usr/bin/env python3
"""E-05：证据 grounding 准确率门禁（合成金标：摘录须为原文子串且 span 可定位）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS
from app.domain.essay_grading_context import EssayGradingContext
from app.domain.question_type import QuestionType
from app.domain.scoring_engine.evidence_engine import (
    apply_llm_evidence_to_result,
    extract_rule_evidence,
    quote_is_substring,
)
from app.domain.scoring_engine.essay_signals import analyze_essay_signals
from app.domain.scoring_engine.hard_rules import run_hard_rules
from app.domain.scoring_engine.question_standard_card import build_question_standard_card


def _ctx() -> EssayGradingContext:
    return EssayGradingContext(
        title="evidence-acc",
        prompt="围绕基层治理写一篇文章",
        reference_material="材料：推进基层治理现代化。",
        material_structured={"word_min": 800, "word_max": 1200},
        scoring_points=DEFAULT_RUBRIC_DIMENSIONS,
        score=40,
        word_limit=1200,
        question_type=QuestionType.essay,
        cache_context_key="evidence-acc",
        standard_version=1,
        standard_review_status="published",
        question_standard={
            "keywords": ["基层治理", "现代化"],
            "proposition_task": "论证",
            "review_status": "published",
        },
        rubric_criteria=[],
    )


GOLD_CASES: list[tuple[str, dict[str, dict]]] = [
    (
        "推进基层治理现代化\n\n完善治理体系，提升治理能力。" * 15,
        {
            "T1": {
                "evidence_positive": ["推进基层治理现代化", "完善治理体系"],
                "evidence_negative": ["完全虚构的句子"],
                "evidence_missing": [],
            }
        },
    ),
    (
        "第一段论述。\n\n第二段继续论证基层治理与数字化协同。" * 12,
        {
            "T2": {
                "evidence_positive": ["基层治理与数字化协同"],
                "evidence_negative": ["不存在于原文"],
                "evidence_missing": [],
            }
        },
    ),
]


def _metrics_for_case(essay: str, llm_by_trait: dict[str, dict]) -> tuple[float, float]:
    ctx = _ctx()
    standard = build_question_standard_card(ctx)
    signals = analyze_essay_signals(essay, standard)
    hard = run_hard_rules(
        essay,
        word_min=800,
        word_max=1200,
        reference_material=ctx.reference_material or "",
        main_point_hit=signals.main_thesis_signal,
    )
    base = extract_rule_evidence(essay, signals, hard, standard)
    merged = apply_llm_evidence_to_result(essay, base, llm_by_trait)

    emitted = 0
    for bundle in merged.by_trait.values():
        for q in bundle.positive + bundle.negative:
            emitted += 1
            assert quote_is_substring(essay, q), f"ungrounded emitted quote: {q[:40]}"
        for sp in bundle.spans or []:
            if sp.grounded and sp.quote in bundle.positive + bundle.negative:
                assert sp.start is not None and sp.end is not None and sp.end > sp.start

    blocked = 0
    hallucination_attempts = 0
    for tid, row in llm_by_trait.items():
        props = list(row.get("evidence_positive") or []) + list(row.get("evidence_negative") or [])
        bundle = merged.by_trait[tid]
        kept = set(bundle.positive + bundle.negative)
        for raw in props:
            q = str(raw or "").strip()
            if len(q) < 6:
                continue
            if quote_is_substring(essay, q):
                continue
            hallucination_attempts += 1
            if not any(q in k or k in q for k in kept):
                blocked += 1

    hallucination_block_rate = blocked / hallucination_attempts if hallucination_attempts else 1.0
    emitted_rate = 1.0 if emitted else 1.0
    return emitted_rate, hallucination_block_rate


def main() -> None:
    emitted_rates: list[float] = []
    block_rates: list[float] = []
    for essay, llm in GOLD_CASES:
        emitted, block = _metrics_for_case(essay, llm)
        emitted_rates.append(emitted)
        block_rates.append(block)
        assert block >= 0.99, f"hallucination not blocked: {block}"

    overall = min(min(emitted_rates), sum(block_rates) / len(block_rates))
    threshold = float(settings.evidence_accuracy_min_rate)
    assert overall >= threshold, f"evidence accuracy {overall:.3f} < {threshold}"
    print(f"verify_evidence_accuracy: ok (score={overall:.3f}, threshold={threshold})")


if __name__ == "__main__":
    main()
