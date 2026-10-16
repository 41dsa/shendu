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
    retry_allowed: bool = True
    retry_limit_message: str | None = None
    retry_max_count: int = 1
    retry_used_count: int = 0
    first_pass_tier_id: str | None = None
    first_pass_tier_label: str | None = None


class RetrySubmitResponse(BaseModel):
    grading_job_id: str
    submission_id: str
    attempt: int
