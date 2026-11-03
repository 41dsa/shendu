"""Phase 5：弱监督工厂 + 主动学习触发（纯逻辑冒烟）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.types import ScoringEngineResult, ScoringTier
from app.models.entities import WeakLabelType
from app.services.active_learning_pool import evaluate_active_learning_triggers
from app.services.weak_supervision_factory import (
    COUNTEREXAMPLE_TEMPLATES,
    labels_from_engine_result,
    weak_label_export_row,
)
from app.models.entities import WeakLabel


def _engine(**kwargs) -> ScoringEngineResult:
    tier = ScoringTier("t4", "四类文", 0, 15)
    base = dict(
        exam_level="municipal",
        level_inferred=True,
        level_config_version="1.0.0",
        point_pool_version="essay-trait-v1.0.0",
        total_score=0.0,
        max_score=40.0,
        tier=tier,
        dimension_rows=[],
        point_hits=[],
        penalties={},
        confidence=0.7,
        level_specific_feedback="",
        evidence_chain=[],
        engine_traces=[],
        trait_diagnostics=[
            {
                "trait_id": "T1",
                "level": "L2",
                "confidence": 0.8,
                "participates_in_score": True,
                "model_votes": [{"model": "a", "level": "L2"}, {"model": "b", "level": "L2"}],
                "vote_spread": 0.0,
            },
            {
                "trait_id": "T4",
                "level": "L2",
                "evidence_insufficient": True,
                "participates_in_score": True,
            },
            {
                "trait_id": "T5",
                "level": "L1",
                "evidence_insufficient": True,
                "participates_in_score": True,
                "model_votes": [{"model": "a", "level": "L0"}, {"model": "b", "level": "L4"}],
                "vote_spread": 1.0,
            },
        ],
        trait_vote_max_spread=0.75,
        trait_confidence=0.55,
        hard_rule_flags={"severe_off_topic": True},
        rubric_version="essay-trait-v1.0.0",
    )
    base.update(kwargs)
    return ScoringEngineResult(**base)


def main() -> None:
    eng = _engine()
    labels = labels_from_engine_result(eng)
    types = {x["label_type"] for x in labels}
    assert WeakLabelType.rule.value in types
    assert WeakLabelType.rubric.value in types
    rubric_rows = [x for x in labels if x["label_type"] == WeakLabelType.rubric.value]
    assert rubric_rows[0]["payload"].get("source") == "trait_rubric_engine"
    assert WeakLabelType.model_consensus.value in types
    assert WeakLabelType.self_consistency.value in types

    triggers = evaluate_active_learning_triggers(eng, standard_match_confidence=0.5)
    reasons = {t[0].value for t in triggers}
    assert "trait_vote_spread" in reasons
    assert "evidence_insufficient" in reasons
    assert "standard_match_low" in reasons

    row = WeakLabel(
        label_type=WeakLabelType.rubric,
        label_value="L2",
        trait_id="T1",
        is_weak_label=True,
    )
    exported = weak_label_export_row(row)
    assert exported["is_weak_label"] is True
    assert exported["label_type"] == "rubric"

    assert len(COUNTEREXAMPLE_TEMPLATES) >= 3
    print("verify_weak_supervision_factory: ok")


if __name__ == "__main__":
    main()
