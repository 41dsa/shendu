#!/usr/bin/env python3
"""M-09：材料锚点句与 Evidence T4 联动。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.evidence_engine import extract_evidence
from app.domain.scoring_engine.essay_signals import analyze_essay_signals
from app.domain.scoring_engine.hard_rules import run_hard_rules
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard


def _card(anchors: list[str]) -> QuestionStandardCard:
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
        material_anchor_phrases=anchors,
        material_facts=[],
        material_logic=[],
        recommended_argument=[],
        recommended_analysis=[],
        recommended_policy=[],
        trait_rubric_adjustments=[],
    )


def main() -> None:
    essay = ("开头。\n\n本文强调网格化管理提升基层效率，推进基层治理现代化。" * 25).strip()
    standard = _card(["网格化管理", "完全未出现的锚点"])
    signals = analyze_essay_signals(essay, standard)
    hard = run_hard_rules(essay, word_min=800, word_max=1200, reference_material="", main_point_hit=True)
    result = extract_evidence(essay, signals, hard, standard)
    t4 = result.by_trait["T4"]
    assert any("网格化" in q for q in t4.positive), t4.positive
    assert any("未覆盖材料锚点" in m for m in t4.missing), t4.missing
    print("verify_material_anchor_evidence: OK")


if __name__ == "__main__":
    main()
