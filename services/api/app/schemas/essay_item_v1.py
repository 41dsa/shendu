"""Q-01 EssayItem V1：真题题干/材料/考试说明等 A 类字段（导入后只读锁定）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# A 类：官方题库导入后不可通过 Admin 随意篡改
ESSAY_ITEM_A_CLASS_FIELDS: frozenset[str] = frozenset(
    {
        "exam",
        "year",
        "question_no",
        "title",
        "prompt",
        "material",
        "exam_instructions",
        "word_min",
        "word_max",
        "score",
    }
)


class EssayItemV1Schema(BaseModel):
    """与 CSV/JSON 导入器统一的 Essay 资源契约。"""

    exam: str = ""
    year: int | None = None
    question_no: int | None = None
    title: str
    prompt: str
    material: str = ""
    exam_instructions: str = ""
    word_min: int = 800
    word_max: int = 1200
    score: int = 40
    document_ids: list[str] = Field(default_factory=list)
    published: bool = True
    source: str = "import"
    import_version: str = "essay-item-v1"

    def a_class_snapshot(self) -> dict[str, Any]:
        return {
            "exam": self.exam,
            "year": self.year,
            "question_no": self.question_no,
            "title": self.title,
            "prompt": self.prompt,
            "material": self.material,
            "exam_instructions": self.exam_instructions,
            "word_min": self.word_min,
            "word_max": self.word_max,
            "score": self.score,
        }
