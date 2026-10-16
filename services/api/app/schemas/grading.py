from pydantic import BaseModel


class GradingJobSubmissionSnapshot(BaseModel):
    """关联提交内容，供批改页在任务失败后回填表单。"""

    submission_id: str
    question_id: str
    is_custom: bool
    user_prompt: str | None = None
    user_material: str | None = None
    exam_level: str | None = None
    content: str = ""


class GradingJobResponse(BaseModel):
    id: str
    status: str
    current_step: str | None
    steps: list[dict]
    error_message: str | None
    report_id: str | None = None
    created_at: str | None = None
    submission: GradingJobSubmissionSnapshot | None = None


class GradingJobListItem(BaseModel):
    id: str
    status: str
    current_step: str | None
    created_at: str
    error_message: str | None = None
    report_id: str | None = None
    label: str = ""


class GradingQueueResponse(BaseModel):
    max_concurrent: int
    active_count: int
    jobs: list[GradingJobListItem]


class ReportSubmissionSnapshot(BaseModel):
    content: str = ""
    user_prompt: str | None = None
    user_material: str | None = None
    question_title: str | None = None
    is_custom: bool = False
    attempt: int = 1


class RewriteDemoResponse(BaseModel):
    report_id: str
    rewrite_demo: dict
    payload: dict


class ReferenceSampleResponse(BaseModel):
    report_id: str
    reference_sample: dict
    payload: dict


class ReportResponse(BaseModel):
    id: str
    payload: dict
    submission: ReportSubmissionSnapshot | None = None


class ReportListItem(BaseModel):
    id: str
    created_at: str
    total_score: float | None = None
    confidence: str | None = None
    grading_job_id: str
