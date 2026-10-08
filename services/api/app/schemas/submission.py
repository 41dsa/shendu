from pydantic import BaseModel, Field


class SubmissionUpsert(BaseModel):
    question_id: str
    content: str = ""
    status: str = "draft"


class SubmissionResponse(BaseModel):
    id: str
    question_id: str
    content: str
    status: str
    attempt: int


class SubmitGradingResponse(BaseModel):
    grading_job_id: str
    submission_id: str
