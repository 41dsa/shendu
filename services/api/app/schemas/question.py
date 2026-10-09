from pydantic import BaseModel, Field


class RubricDimensionSchema(BaseModel):
    id: str
    label: str
    max_score: int = 10
    required: bool = True


class QuestionListItem(BaseModel):
    id: str
    title: str
    question_type: str
    question_type_label: str = "申论大作文"
    score: int
    word_limit: int
    word_min: int | None = None
    word_max: int | None = None
    exam: str | None = None
    year: int | None = None
    has_published_standard: bool = False


class QuestionDetail(QuestionListItem):
    prompt: str
    reference_material: str | None = Field(None, description="可选参考背景")
    scoring_points: list[RubricDimensionSchema] = Field(default_factory=list)
