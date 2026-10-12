"""自备批改走标准引擎：冒烟。"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.models.entities import Question, QuestionType, Submission
from app.services.essay_context import resolve_essay_context
from app.services.standard_engine.custom_essay_standard import ensure_custom_essay_standard


def main() -> None:
    db = SessionLocal()
    try:
        q = db.get(Question, USER_ESSAY_QUESTION_ID)
        if not q:
            print("skip: run init_db (sys-user-essay missing)")
            return
        sub = Submission(
            user_id="verify-user",
            question_id=USER_ESSAY_QUESTION_ID,
            user_prompt="请围绕「基层治理现代化」自拟题目写一篇文章，800～1000字。",
            user_material="某市推进网格化管理，也存在职责交叉问题。",
            content="占位",
        )
        db.add(sub)
        db.flush()
        payload = asyncio.run(
            ensure_custom_essay_standard(
                db,
                sub,
                q,
                user_id=sub.user_id,
                grading_job_id="verify-job",
            )
        )
        assert payload and payload.get("rubric_standard"), payload
        ctx = resolve_essay_context(sub, q, db)
        assert ctx.standard_version == 1, ctx.standard_version
        assert len(ctx.rubric_criteria) >= 1, ctx.rubric_criteria
        assert len(ctx.scoring_points) >= 4, ctx.scoring_points
        db.rollback()
        print("verify_custom_essay_standard: ok")
    finally:
        db.close()


if __name__ == "__main__":
    main()
