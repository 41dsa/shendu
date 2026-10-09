"""Create tables, migrate lightweight columns, seed demo 大作文 + test redeem code."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.entities import PromptPurpose, PromptVersion, Question, QuestionType, RedeemCode, RedeemCodeStatus
from app.services.grading_service import SYSTEM_PROMPT

DEV_TEST_CODE = "TEST-DEV-LICENSE"
DEMO_QUESTION_ID = "demo-essay-001"

DEMO_ESSAY = Question(
    id=DEMO_QUESTION_ID,
    title="2024 国考副省级：数字化与治理能力",
    question_type=QuestionType.essay,
    score=40,
    word_limit=1200,
    prompt=(
        "请结合给定材料，联系实际，围绕「以数字化提升治理效能」这一主题，"
        "自拟题目，写一篇文章。\n\n"
        "要求：（1）观点明确，见解深刻；（2）思路清晰，语言流畅；"
        "（3）参考给定材料，但不拘泥于材料；（4）字数 800～1200 字。"
    ),
    material=(
        "【参考背景，非小题阅读】某市建设「城市大脑」，推动一网通办；"
        "同时也出现数据孤岛、重建设轻运营、基层不会用等问题。"
    ),
    material_structured={
        "genre": "essay",
        "word_min": 800,
        "word_max": 1200,
        "exam": "国考副省级",
    },
    scoring_points=[
        {"id": "D01", "label": "立意与观点", "max_score": 10, "required": True, "ability": "A1"},
        {"id": "D02", "label": "结构与层次", "max_score": 10, "required": True, "ability": "A2"},
        {"id": "D03", "label": "论证与素材", "max_score": 10, "required": True, "ability": "A3"},
        {"id": "D04", "label": "语言表达", "max_score": 10, "required": True, "ability": "A4"},
    ],
)


def ensure_question_columns() -> None:
    insp = inspect(engine)
    if "questions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("questions")}
    with engine.begin() as conn:
        if "prompt" not in cols:
            conn.execute(text("ALTER TABLE questions ADD COLUMN prompt TEXT DEFAULT ''"))
        conn.execute(
            text(
                "UPDATE questions SET question_type = 'essay' "
                "WHERE question_type IN ('summarize', 'analysis', 'countermeasure')"
            )
        )
        conn.execute(text("DELETE FROM questions WHERE title = '基层治理存在问题归纳'"))


def ensure_submission_columns() -> None:
    insp = inspect(engine)
    if "submissions" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("submissions")}
    with engine.begin() as conn:
        if "parent_submission_id" not in cols:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN parent_submission_id VARCHAR(36)"))
        if "attempt" not in cols:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN attempt INTEGER DEFAULT 1"))


def upsert_demo_essay(db) -> None:
    row = db.get(Question, DEMO_QUESTION_ID)
    if row:
        row.title = DEMO_ESSAY.title
        row.question_type = QuestionType.essay
        row.score = DEMO_ESSAY.score
        row.word_limit = DEMO_ESSAY.word_limit
        row.prompt = DEMO_ESSAY.prompt
        row.material = DEMO_ESSAY.material
        row.material_structured = DEMO_ESSAY.material_structured
        row.scoring_points = DEMO_ESSAY.scoring_points
        row.published = True
        return
    legacy = db.query(Question).filter(Question.title == "基层治理存在问题归纳").all()
    for old in legacy:
        db.delete(old)
    db.add(DEMO_ESSAY)


def seed_default_prompt(db) -> None:
    if db.query(PromptVersion).first():
        return
    db.add(
        PromptVersion(
            name="内置大作文批改 v1",
            purpose=PromptPurpose.essay_grading,
            content=SYSTEM_PROMPT,
            is_active=True,
        )
    )


def main() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_question_columns()
    ensure_submission_columns()
    db = SessionLocal()
    try:
        upsert_demo_essay(db)
        seed_default_prompt(db)
        dev_code = db.get(RedeemCode, DEV_TEST_CODE)
        if not dev_code:
            db.add(RedeemCode(code=DEV_TEST_CODE, sku="lifetime_web", batch_id="dev"))
        elif settings.app_env == "development":
            dev_code.status = RedeemCodeStatus.unused
            dev_code.used_by_user_id = None
            dev_code.used_at = None
        db.commit()
        print(f"DB initialized. Demo: 申论大作文 ({DEMO_QUESTION_ID}). Test code: {DEV_TEST_CODE}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
