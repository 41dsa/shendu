from pydantic import BaseModel


class GradingJobResponse(BaseModel):
    id: str
    status: str
    current_step: str | None
    steps: list[dict]
    error_message: str | None
    report_id: str | None = None


class ReportResponse(BaseModel):
    id: str
    payload: dict


class ReportListItem(BaseModel):
    id: str
    created_at: str
    total_score: float | None = None
    confidence: str | None = None
    grading_job_id: str
