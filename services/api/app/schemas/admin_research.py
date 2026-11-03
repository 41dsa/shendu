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


class PromptVersionUpdate(BaseModel):
    name: str | None = None
    content: str | None = None


class GoldSampleCreate(BaseModel):
    question_id: str
    title: str
    reference_answer: str
    expected_score_min: int | None = None
    expected_score_max: int | None = None
    note: str | None = None


class DisputeCreate(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class PairCompareCreate(BaseModel):
    question_id: str
    submission_a_id: str
    submission_b_id: str
    trait_id: str | None = None


class PairCompareComplete(BaseModel):
    preferred_submission_id: str
    trait_id: str | None = None
    note: str = ""


class AnchorEssayUpsert(BaseModel):
    question_id: str
    title: str = ""
    content: str = Field(min_length=20)
    aggregate_level: str = "L2"
    trait_levels: dict[str, str] = Field(default_factory=dict)
    is_published: bool = True


class AnchorTraitReviewCreate(BaseModel):
    reviewer_label: str = "reviewer_1"
    trait_id: str
    level: str = "L2"
    evidence_positive: list[str] = Field(default_factory=list)
    reviewer_rationale: str = ""
    dispute_note: str = ""


class AnchorTraitReviewBatchItem(BaseModel):
    trait_id: str
    evidence_positive: list[str] = Field(default_factory=list)
    reviewer_rationale: str = ""


class AnchorTraitReviewBatchCreate(BaseModel):
    """同一评者一次提交多个维度（共享档位与争议说明；证据可按维度分别提交）。"""

    reviewer_label: str
    level: str = "L2"
    dispute_note: str = ""
    items: list[AnchorTraitReviewBatchItem] = Field(default_factory=list)
    trait_ids: list[str] = Field(default_factory=list, max_length=8)
    evidence_positive: list[str] = Field(default_factory=list)


class AnchorEssayPatch(BaseModel):
    title: str | None = None
    is_published: bool | None = None
    aggregate_level: str | None = None
    trait_levels: dict[str, str] | None = None
