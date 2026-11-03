#!/usr/bin/env python3
"""D-01：Trait 评分记录双写（trait_scoring_records + hit_log trait_v1）。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.types import ScoringEngineResult, ScoringTier
from app.models.entities import ScoringPointHitLog, TraitScoringRecord
from app.services.scoring_engine.feedback_log import persist_trait_scoring_records


def _engine() -> ScoringEngineResult:
    tier = ScoringTier("t4", "四类文", 0, 15)
    traits = [
        {
            "trait_id": f"T{i}",
            "level": "L2",
            "confidence": 0.8,
            "participates_in_score": i <= 5,
            "evidence_positive": ["摘录"],
            "model_votes": [{"model": "primary", "level": "L2"}],
            "vote_spread": 0.0,
        }
        for i in range(1, 9)
    ]
    return ScoringEngineResult(
        exam_level="municipal",
        level_inferred=True,
        level_config_version="1.0.0",
        point_pool_version="essay-trait-v1.0.1",
        total_score=28.0,
        max_score=40.0,
        tier=tier,
        dimension_rows=[],
        point_hits=[],
        penalties={},
        confidence=0.8,
        level_specific_feedback="",
        evidence_chain=[],
        engine_traces=[],
        trait_diagnostics=traits,
        rubric_version="essay-trait-v1.0.1",
        standard_match_confidence=0.92,
        system_center_score=28.0,
    )


def main() -> None:
    from app.config import settings

    settings.weak_supervision_enabled = False
    db = MagicMock()
    persist_trait_scoring_records(
        db,
        grading_job_id="job-1",
        submission_id="sub-1",
        question_id="demo-essay-001",
        result=_engine(),
    )
    added = [c.args[0] for c in db.add.call_args_list]
    trait_rows = [x for x in added if isinstance(x, TraitScoringRecord)]
    hit_rows = [x for x in added if isinstance(x, ScoringPointHitLog)]
    assert len(trait_rows) == 8
    assert len(hit_rows) == 8
    assert trait_rows[0].trait_id == "T1"
    assert hit_rows[0].payload.get("record_type") == "trait_v1"
    assert trait_rows[0].final_calibrated_score is None
    print("verify_trait_scoring_records: OK")


if __name__ == "__main__":
    main()
