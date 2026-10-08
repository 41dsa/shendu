from pydantic import BaseModel, Field


class RetrySubmitBody(BaseModel):
    content: str = Field(min_length=10)


class RetryContextResponse(BaseModel):
    report_id: str
    question_id: str
    question_title: str
    prompt: str
    first_content: str
    first_score: float | None
    issues: list[dict]
    suggestions: list[str]
    attempt_next: int


class RetrySubmitResponse(BaseModel):
    grading_job_id: str
    submission_id: str
    attempt: int


class TrainingStartBody(BaseModel):
    kind: str
    title: str
    level: str = "L1"
    ability_id: str | None = None
    focus_tag: str | None = None
    instructions: str | None = None
    question_id: str | None = None


class TrainingCompleteBody(BaseModel):
    result_note: str | None = None
    linked_report_id: str | None = None
