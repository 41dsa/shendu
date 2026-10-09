import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models.entities import PromptPurpose, UserProviderCredential
from app.services.ai_client import AiCallError, chat_completion_json
from app.services.standard_engine.prompt_service import get_active_standard_prompt
from app.services.standard_engine.usage import log_standard_gen_usage


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


async def call_standard_llm(
    db: Session,
    *,
    cred: UserProviderCredential,
    purpose: PromptPurpose,
    user_payload: dict[str, Any],
    user_id: str,
    job_id: str,
    call_type: str,
    max_retries: int = 2,
) -> tuple[dict[str, Any], str | None]:
    system = get_active_standard_prompt(db, purpose)
    user = json.dumps(user_payload, ensure_ascii=False)
    last_raw = ""
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            raw, usage = await chat_completion_json(cred, system, user)
            last_raw = raw
            data = extract_json_object(raw)
            log_standard_gen_usage(
                db, user_id=user_id, job_id=job_id, cred=cred, usage=usage, call_type=call_type
            )
            return data, raw
        except (json.JSONDecodeError, AiCallError) as exc:
            last_err = exc
            system = system + "\n\n上次输出无效，请仅输出一个合法 JSON 对象。"
        except Exception as exc:
            last_err = exc
    raise ValueError(f"LLM JSON 失败 ({purpose.value}): {last_err}; raw={last_raw[:200]}")


def validate_model(model: type[BaseModel], data: dict[str, Any]) -> BaseModel:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
