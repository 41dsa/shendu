from pydantic import BaseModel, Field


class SubmissionUpsert(BaseModel):
    """题库题：传 question_id；自备题：传 user_prompt（材料可选 user_material）。"""

    question_id: str | None = None
    user_prompt: str | None = None
    user_material: str | None = None
    content: str = ""
    status: str = "draft"


class SubmissionResponse(BaseModel):
    id: str
    question_id: str
    user_prompt: str | None = None
    user_material: str | None = None
    content: str
    status: str
    attempt: int


class SubmitGradingResponse(BaseModel):
    grading_job_id: str
    submission_id: str
