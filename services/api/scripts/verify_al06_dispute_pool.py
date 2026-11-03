#!/usr/bin/env python3
"""AL-06：用户申诉/争议入主动学习池。"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.entities import ActiveLearningPoolEntry, ActiveLearningReason
from app.services.active_learning_pool import enqueue_dispute_sample


def main() -> None:
    db = MagicMock()
    enqueue_dispute_sample(
        db,
        report_id="r1",
        submission_id="s1",
        question_id="q1",
        reason_text="分数与自评差距大，请复核",
    )
    row = db.add.call_args.args[0]
    assert isinstance(row, ActiveLearningPoolEntry)
    assert row.reason == ActiveLearningReason.user_dispute
    assert row.priority >= 0.8
    assert row.snapshot.get("report_id") == "r1"
    assert "dispute_reason" in row.snapshot
    print("verify_al06_dispute_pool: OK")


if __name__ == "__main__":
    main()
