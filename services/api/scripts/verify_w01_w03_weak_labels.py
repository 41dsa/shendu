#!/usr/bin/env python3
"""W-01 / W-03：规则弱标签 + 多模型高共识弱标签。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.types import ScoringEngineResult, ScoringTier
from app.models.entities import WeakLabelType
from app.services.weak_supervision_factory import labels_from_engine_result


def _engine(**kwargs) -> ScoringEngineResult:
    tier = ScoringTier("t4", "四类文", 0, 15)
    traits = [
        {
            "trait_id": "T1",
            "level": "L2",
            "model_votes": [{"model": "a", "level": "L2"}, {"model": "b", "level": "L2"}],
            "vote_spread": 0.0,
        },
        {
            "trait_id": "T5",
            "level": "L2",
            "model_votes": [{"model": "a", "level": "L2"}, {"model": "b", "level": "L2"}],
            "vote_spread": 0.0,
        },
    ]
    base = dict(
        exam_level="municipal",
        level_inferred=True,
        level_config_version="1.0.0",
        point_pool_version="essay-trait-v1.0.1",
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
        trait_diagnostics=traits,
        hard_rule_flags={"word_short": True},
        trait_vote_max_spread=0.0,
        rubric_version="essay-trait-v1.0.1",
    )
    base.update(kwargs)
    return ScoringEngineResult(**base)


def main() -> None:
    labels = labels_from_engine_result(_engine())
    types = {x["label_type"] for x in labels}
    assert WeakLabelType.rule.value in types
    assert WeakLabelType.model_consensus.value in types
    per_trait = [x for x in labels if x["label_type"] == WeakLabelType.model_consensus.value and x.get("trait_id")]
    engine_level = [x for x in labels if x.get("label_value") == "engine_high_consensus"]
    assert per_trait
    assert engine_level
    print("verify_w01_w03_weak_labels: OK")


if __name__ == "__main__":
    main()
