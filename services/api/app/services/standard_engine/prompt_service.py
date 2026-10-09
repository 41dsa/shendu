from sqlalchemy.orm import Session

from app.models.entities import PromptPurpose, PromptVersion
from app.services.standard_engine.prompt_defaults import STANDARD_PROMPT_BODIES


def get_active_standard_prompt(db: Session, purpose: PromptPurpose) -> str:
    row = (
        db.query(PromptVersion)
        .filter(PromptVersion.purpose == purpose, PromptVersion.is_active.is_(True))
        .first()
    )
    if row:
        return row.content
    return STANDARD_PROMPT_BODIES.get(purpose.value, "仅输出 JSON。")
