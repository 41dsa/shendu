import json
import re

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


def normalize_base_url(base_url: str) -> str:
    """OpenAI 兼容：DeepSeek 等需带 /v1 后缀。"""
    u = base_url.rstrip("/")
    if re.match(r"^https://api\.deepseek\.com$", u):
        return u + "/v1"
    if u.endswith("/v1"):
        return u
    return u


def chat_completions_url(base_url: str) -> str:
    return normalize_base_url(base_url) + "/chat/completions"


def _upstream_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])[:300]
        if isinstance(err, str):
            return err[:300]
        return json.dumps(body, ensure_ascii=False)[:300]
    except Exception:
        return (resp.text or resp.reason_phrase or "")[:300]


def _raise_for_response(resp: httpx.Response, *, context: str) -> None:
    if resp.status_code in (401, 403):
        raise AiCallError("INVALID_KEY", "API Key 无效或无权限")
    if resp.status_code == 429:
        raise AiCallError("RATE_LIMIT", "请求过于频繁或余额不足")
    if resp.status_code >= 400:
        hint = _upstream_message(resp)
        extra = f"：{hint}" if hint else ""
        if resp.status_code == 400:
            raise AiCallError(
                "UPSTREAM",
                f"{context} ({resp.status_code}){extra}。"
                "请检查 Base URL（DeepSeek 建议 https://api.deepseek.com/v1）、模型名、"
                "以及是否支持 JSON 模式；先在 AI 设置点「测试连接」。",
            )
        raise AiCallError("UPSTREAM", f"{context} ({resp.status_code}){extra}")


async def test_connection(cred: UserProviderCredential) -> dict:
    """与批改一致：带 json_object，避免「测试通过、批改 400」。"""
    api_key = decrypt_api_key(cred)
    url = chat_completions_url(cred.base_url)
    payload = {
        "model": cred.model,
        "messages": [
            {"role": "system", "content": "只输出 JSON：{\"ok\": true}"},
            {"role": "user", "content": "ping"},
        ],
        "max_tokens": 16,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise AiCallError("NETWORK", str(exc)) from exc

    if resp.status_code == 400:
        payload.pop("response_format", None)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp2 = await client.post(url, json=payload, headers=headers)
        if resp2.status_code < 400:
            return {
                "ok": True,
                "status_code": resp2.status_code,
                "json_mode": False,
                "warning": "当前模型不支持 response_format=json_object，批改将使用兼容模式。",
            }
        _raise_for_response(resp2, context="模型服务错误")
    _raise_for_response(resp, context="模型服务错误")
    return {"ok": True, "status_code": resp.status_code, "json_mode": True}


async def chat_completion_json(cred: UserProviderCredential, system: str, user: str) -> tuple[str, dict | None]:
    api_key = decrypt_api_key(cred)
    url = chat_completions_url(cred.base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    async def _post(payload: dict) -> httpx.Response:
        async with httpx.AsyncClient(timeout=120.0) as client:
            return await client.post(url, json=payload, headers=headers)

    payload_json = {
        "model": cred.model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    resp = await _post(payload_json)
    if resp.status_code == 400:
        system_compat = system + "\n\n你必须只输出一个合法 JSON 对象，不要 Markdown 代码块。"
        payload_plain = {
            "model": cred.model,
            "messages": [
                {"role": "system", "content": system_compat},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
        }
        resp = await _post(payload_plain)

    if resp.status_code >= 400:
        _raise_for_response(resp, context="模型调用失败")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage")
    return content, usage
