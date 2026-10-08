import httpx

from app.core.crypto import decrypt_secret
from app.models.entities import CredentialRole, UserProviderCredential


class AiCallError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def get_credential(db, user_id: str, role: CredentialRole) -> UserProviderCredential | None:
    return (
        db.query(UserProviderCredential)
        .filter(UserProviderCredential.user_id == user_id, UserProviderCredential.role == role)
        .first()
    )


def decrypt_api_key(cred: UserProviderCredential) -> str:
    return decrypt_secret(cred.api_key_nonce, cred.api_key_ciphertext)


async def test_connection(cred: UserProviderCredential) -> dict:
    api_key = decrypt_api_key(cred)
    url = cred.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cred.model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 5,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise AiCallError("NETWORK", str(exc)) from exc

    if resp.status_code in (401, 403):
        raise AiCallError("INVALID_KEY", "API Key 无效或无权限")
    if resp.status_code == 429:
        raise AiCallError("RATE_LIMIT", "请求过于频繁或余额不足")
    if resp.status_code >= 400:
        raise AiCallError("UPSTREAM", f"模型服务错误 ({resp.status_code})")
    return {"ok": True, "status_code": resp.status_code}


async def chat_completion_json(cred: UserProviderCredential, system: str, user: str) -> tuple[str, dict | None]:
    api_key = decrypt_api_key(cred)
    url = cred.base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": cred.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
    if resp.status_code >= 400:
        raise AiCallError("UPSTREAM", f"模型调用失败 ({resp.status_code})")
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage")
    return content, usage
