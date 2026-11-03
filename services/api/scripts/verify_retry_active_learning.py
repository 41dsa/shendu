#!/usr/bin/env python3
"""AL-02：重作 Trait 波动触发主动学习入池逻辑。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.active_learning_pool import compute_trait_retry_deltas, evaluate_active_learning_triggers
from app.domain.scoring_engine.types import ScoringEngineResult, ScoringTier


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
        trait_diagnostics=[],
        rubric_version="essay-trait-v1.0.0",
    )
    base.update(kwargs)
    return ScoringEngineResult(**base)


def main() -> None:
    prior = [{"trait_id": "T1", "level": "L2"}, {"trait_id": "T5", "level": "L3"}]
    current = [{"trait_id": "T1", "level": "L0"}, {"trait_id": "T5", "level": "L1"}]
    deltas = compute_trait_retry_deltas(prior, current)
    assert len(deltas) == 2
    assert abs(deltas[0]["delta_numeric"]) >= 1

    eng = _engine(
        trait_diagnostics=[
            {"trait_id": "T1", "level": "L2", "confidence": 0.55},
            {"trait_id": "T2", "level": "L2", "confidence": 0.58},
            {"trait_id": "T3", "level": "L3", "confidence": 0.8},
        ],
    )
    triggers = evaluate_active_learning_triggers(eng, standard_match_confidence=0.9)
    assert any(t[0].value == "level_boundary" for t in triggers)
    print("verify_retry_active_learning: OK")


if __name__ == "__main__":
    main()
