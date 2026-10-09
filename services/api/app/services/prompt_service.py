"""生效 Prompt 解析（BE-603）：DB 中 is_active 优先，否则回退代码内默认。"""

from sqlalchemy.orm import Session

from app.models.entities import PromptPurpose, PromptVersion


def get_active_grading_system_prompt(db: Session, fallback: str) -> str:
    row = (
        db.query(PromptVersion)
        .filter(PromptVersion.purpose == PromptPurpose.essay_grading, PromptVersion.is_active.is_(True))
        .first()
    )
    return row.content if row else fallback
