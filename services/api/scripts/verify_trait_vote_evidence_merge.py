#!/usr/bin/env python3
"""E-02：投票模型 evidence 聚合与子串 grounding 冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.evidence_engine import apply_llm_evidence_to_result, extract_rule_evidence
from app.domain.scoring_engine.essay_signals import analyze_essay_signals
from app.domain.scoring_engine.hard_rules import run_hard_rules
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard


def _card() -> QuestionStandardCard:
    return QuestionStandardCard(
        question_id="q",
        version=1,
        review_status="published",
        reviewed=True,
        theme="t",
        task="论证",
        keywords=["基层"],
        keyword_relations=[],
        core_problem="",
        core_theses=[],
        acceptable_theses=[],
        edge_theses=[],
        off_topic_hints=[],
        severe_off_topic_hints=[],
        material_anchor_phrases=[],
        material_facts=[],
        material_logic=[],
        recommended_argument=[],
        recommended_analysis=[],
        recommended_policy=[],
        trait_rubric_adjustments=[],
    )


def main() -> None:
    essay = ("推进基层治理现代化\n\n完善治理体系。" * 30).strip()
    standard = _card()
    signals = analyze_essay_signals(essay, standard)
    hard = run_hard_rules(essay, word_min=800, word_max=1200, reference_material="", main_point_hit=True)
    base = extract_rule_evidence(essay, signals, hard, standard)
    llm = {
        "T1": {
            "evidence_positive": ["推进基层治理现代化", "虚构句子不存在"],
            "evidence_negative": [],
            "evidence_missing": [],
        }
    }
    merged = apply_llm_evidence_to_result(essay, base, llm)
    t1 = merged.by_trait["T1"]
    assert "推进基层治理现代化" in t1.positive
    assert not any("虚构" in q for q in t1.positive)
    print("verify_trait_vote_evidence_merge: OK")


if __name__ == "__main__":
    main()
