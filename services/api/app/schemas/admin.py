from pydantic import BaseModel, Field


class GenerateCodesRequest(BaseModel):
    count: int = Field(ge=1, le=500, default=10)
    batch_id: str | None = None


class GenerateCodesResponse(BaseModel):
    batch_id: str
    codes: list[str]
    unused_total: int


class AdminGrantRequest(BaseModel):
    user_email: str
    sku: str = "lifetime_web"
