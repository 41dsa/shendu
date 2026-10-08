from pydantic import BaseModel, Field


class ExamProfileUpsert(BaseModel):
    exam_type: str = Field(max_length=64)
    province: str = Field(max_length=64)
    year: int = Field(ge=2020, le=2035)
    job_category: str = Field(max_length=64)


class ExamProfileResponse(ExamProfileUpsert):
    id: str
