from pydantic import BaseModel, Field


class AiCredentialUpsert(BaseModel):
    base_url: str = Field(max_length=512)
    model: str = Field(max_length=128)
    api_key: str | None = Field(default=None, max_length=512)
    save_tokens_mode: bool = False


class AiCredentialView(BaseModel):
    role: str
    base_url: str
    model: str
    api_key_masked: str
    configured: bool


class AiTestConnectionRequest(BaseModel):
    role: str = "primary"
