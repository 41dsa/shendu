#!/usr/bin/env python3
"""A-03：标准卡 must_avoid / must_address 与 hard_rules scope_violation 对齐。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.hard_rules import run_hard_rules
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard


def main() -> None:
    essay = ("讨论单一经济话题" * 40).strip()
    hard = run_hard_rules(
        essay,
        word_min=800,
        word_max=1200,
        reference_material="",
        main_point_hit=True,
        must_address=["基层治理", "现代化"],
        must_avoid=["严禁写经济单线"],
    )
    assert hard.flags.get("scope_violation") or hard.format_issues

    card = QuestionStandardCard(
        question_id="q",
        version=1,
        review_status="published",
        reviewed=True,
        theme="基层治理",
        task="论证",
        keywords=["基层治理"],
        keyword_relations=[],
        core_problem="",
        core_theses=["基层治理"],
        acceptable_theses=[],
        edge_theses=[],
        off_topic_hints=["严禁写经济单线"],
        severe_off_topic_hints=[],
        material_anchor_phrases=[],
        material_facts=[],
        material_logic=[],
        recommended_argument=[],
        recommended_analysis=[],
        recommended_policy=[],
        trait_rubric_adjustments=[],
    )
    must_avoid = list(card.off_topic_hints) + list(card.severe_off_topic_hints)
    must_address = list(card.core_theses) + list(card.keywords)[:6]
    hard2 = run_hard_rules(
        essay,
        word_min=800,
        word_max=1200,
        reference_material="",
        main_point_hit=True,
        must_avoid=must_avoid,
        must_address=must_address,
    )
    assert hard2.flags.get("scope_violation") or hard2.format_issues
    print("verify_a03_scope_hard_rules: OK")


if __name__ == "__main__":
    main()
