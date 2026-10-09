from typing import Any

from pydantic import BaseModel, Field


class AdminQuestionUpsert(BaseModel):
    title: str
    prompt: str
    material: str | None = None
    score: int = 40
    word_limit: int = 1200
    word_min: int = 800
    word_max: int = 1200
    scoring_points: list[dict[str, Any]] = Field(default_factory=list)
    published: bool = True


class PromptVersionCreate(BaseModel):
    name: str
    content: str
    purpose: str = "essay_grading"


class GoldSampleCreate(BaseModel):
    question_id: str
    title: str
    reference_answer: str
    expected_score_min: int | None = None
    expected_score_max: int | None = None
    note: str | None = None


class DisputeCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)
