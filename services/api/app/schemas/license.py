from pydantic import BaseModel, Field


class RedeemRequest(BaseModel):
    code: str = Field(min_length=6, max_length=32)


class RedeemResponse(BaseModel):
    ok: bool
    sku: str
    message: str


class PurchaseInfoResponse(BaseModel):
    afdian_plan_url: str
    instructions: str
