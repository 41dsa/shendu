"""Admin Prompt 版本名称规范化（消除「大作文批改」笼统命名）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import PromptPurpose, PromptVersion

_RENAMES: dict[str, str] = {
    "内置大作文批改 v1": "【参考·勿生效】旧版 LLM 主评 v1",
    "报告撰写prompt": "Trait 路径 · 报告撰写（推荐生效）",
    "报告撰写 Prompt": "Trait 路径 · 报告撰写（推荐生效）",
    "自备批改·四档阅卷 v1": "自备四档 · 主评 v1（默认稿）",
}


def normalize_prompt_version_display_names(db: Session) -> int:
    changed = 0
    for old, new in _RENAMES.items():
        rows = db.query(PromptVersion).filter(PromptVersion.name == old).all()
        for row in rows:
            row.name = new
            changed += 1
    if changed:
        db.commit()
    return changed
