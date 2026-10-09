from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import UserAiUsage, UserProviderCredential


def log_standard_gen_usage(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    cred: UserProviderCredential,
    usage: dict[str, Any] | None,
    call_type: str,
) -> None:
    db.add(
        UserAiUsage(
            user_id=user_id,
            standard_generation_job_id=job_id,
            model=cred.model,
            provider_base_url=cred.base_url,
            tokens_in=usage.get("prompt_tokens") if usage else None,
            tokens_out=usage.get("completion_tokens") if usage else None,
            call_type=call_type,
        )
    )
