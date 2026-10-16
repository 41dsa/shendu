from pydantic import BaseModel, Field


class ExamProfileUpsert(BaseModel):
    exam_type: str = Field(max_length=64, description="guokao | shengkao（兼容旧版中文）")
    province: str = Field(max_length=64)
    year: int = Field(ge=2020, le=2035)
    job_category: str = Field(max_length=64, description="卷种/职位层级代码")


class ExamProfileResponse(ExamProfileUpsert):
    id: str
    summary: str | None = None
    mapped_bank_exam: str | None = None
    mapped_bank_year: int | None = None
    suggested_custom_exam_level: str | None = None
