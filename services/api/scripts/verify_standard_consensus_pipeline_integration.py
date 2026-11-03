#!/usr/bin/env python3
"""M-11：三模型标准共识流水线集成（mock 三路由，无 LLM）。"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import Question
from app.schemas.standard_engine import QuestionStandardSchema, ThesisScopeSchema
from app.services.standard_engine.standard_consensus_pipeline import run_standard_consensus_pipeline
from app.services.standard_engine.structure_service import build_structured_essay


def _three_standards(qid: str) -> list[tuple[str, QuestionStandardSchema]]:
    base = QuestionStandardSchema(
        question_id=qid,
        proposition_task="论证观点",
        thesis_scope=ThesisScopeSchema(must_address=["基层治理", "现代化"]),
        keywords=["基层治理"],
    )
    v2 = base.model_copy(deep=True)
    v2.keywords = ["基层治理", "数字化"]
    v3 = base.model_copy(deep=True)
    v3.keywords = ["基层治理", "网格化"]
    return [("primary", base), ("consensus", v2), ("reviewer", v3)]


async def _mock_collect(db, *, essay, user_id, job_id):
    return _three_standards(essay.question_id)


def main() -> None:
    db = SessionLocal()
    try:
        q = db.get(Question, "demo-essay-001")
        assert q, "demo-essay-001 missing"
        essay = build_structured_essay(db, q)
        with patch(
            "app.services.standard_engine.standard_consensus_pipeline.collect_three_question_standards",
            side_effect=_mock_collect,
        ):
            _, card, meta = asyncio.run(
                run_standard_consensus_pipeline(db, essay=essay, user_id="admin-test", job_id="job-test")
            )
        assert meta.model_count == 3
        assert meta.consensus_score > 0.4
        assert "基层治理" in card.keywords
        assert card.review_status in ("draft", "published")
        assert meta.model_labels == ["primary", "consensus", "reviewer"]
        print("verify_standard_consensus_pipeline_integration: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
