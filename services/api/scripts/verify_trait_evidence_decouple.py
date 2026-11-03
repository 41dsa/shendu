#!/usr/bin/env python3
"""E-06：幻觉 LLM 证据不得改变 Trait 等级（Evidence → Rubric 解耦）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.question_standard_card import QuestionStandardCard
from app.domain.scoring_engine.trait_pipeline import run_trait_pipeline


def _standard() -> QuestionStandardCard:
    return QuestionStandardCard(
        question_id="q",
        version=1,
        review_status="published",
        reviewed=True,
        theme="基层治理",
        task="论证",
        keywords=["基层治理", "现代化"],
        keyword_relations=[],
        core_problem="推进基层治理现代化",
        core_theses=["基层治理"],
        acceptable_theses=[],
        edge_theses=[],
        off_topic_hints=[],
        severe_off_topic_hints=[],
        material_anchor_phrases=["网格化"],
        material_facts=[],
        material_logic=[],
        recommended_argument=[],
        recommended_analysis=[],
        recommended_policy=[],
        trait_rubric_adjustments=[],
        match_confidence=0.9,
    )


def main() -> None:
    essay = ("围绕基层治理现代化\n\n推进网格化管理，完善治理体系。" * 22).strip()
    std = _standard()
    base = run_trait_pipeline(
        essay,
        std,
        word_min=800,
        word_max=1200,
        reference_material="材料：网格化管理",
        max_score=40.0,
        word_ratio=1.0,
    )
    with_hallucination = run_trait_pipeline(
        essay,
        std,
        word_min=800,
        word_max=1200,
        reference_material="材料：网格化管理",
        max_score=40.0,
        word_ratio=1.0,
        llm_evidence_by_trait={
            "T1": {
                "evidence_positive": ["完全不在原文的幻觉摘录"],
                "evidence_negative": [],
                "evidence_missing": [],
            }
        },
    )
    base_levels = {d.trait_id: d.level for d in base.diagnostics}
    hall_levels = {d.trait_id: d.level for d in with_hallucination.diagnostics}
    assert base_levels == hall_levels, (base_levels, hall_levels)
    assert not any("幻觉" in q for q in with_hallucination.evidence.by_trait["T1"].positive)
    print("verify_trait_evidence_decouple: OK")


if __name__ == "__main__":
    main()
