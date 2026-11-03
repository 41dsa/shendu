#!/usr/bin/env python3
"""W-07：重作 Trait delta 弱标签结构化写入。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.entities import WeakLabel, WeakLabelType
from app.services.weak_supervision_factory import persist_retry_trait_delta


def main() -> None:
    db = MagicMock()
    n = persist_retry_trait_delta(
        db,
        grading_job_id="j1",
        submission_id="s1",
        question_id="q1",
        prior_traits=[{"trait_id": "T1", "level": "L2"}, {"trait_id": "T5", "level": "L3"}],
        current_traits=[{"trait_id": "T1", "level": "L1"}, {"trait_id": "T5", "level": "L3"}],
        rubric_version="essay-trait-v1.0.1",
    )
    assert n == 1
    row = db.add.call_args.args[0]
    assert isinstance(row, WeakLabel)
    assert row.label_type == WeakLabelType.retry_delta
    assert row.trait_id == "T1"
    assert "L2->L1" in row.label_value
    assert row.payload.get("delta_numeric") == -1
    print("verify_w07_retry_weak_label: OK")


if __name__ == "__main__":
    main()
