"""B/C 档 Trait：LLM 仅抽取原文证据（禁止总分）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.trait_definitions import TRAIT_SPECS
from app.models.entities import CredentialRole
from app.services.ai_client import chat_completion_json, get_credential
from app.services.essay_context import EssayGradingContext

EVIDENCE_PROMPT = """你是申论大作文 Evidence 抽取员。仅输出 JSON，禁止 total_score 与 Trait 等级。
{
  "traits": [
    {
      "trait_id": "T1"|...|"T8",
      "evidence_positive": [string],
      "evidence_negative": [string],
      "evidence_missing": [string]
    }
  ]
}
规则：positive/negative 必须是用户作文原文连续子串（15～120字）；missing 为短中文说明（非虚构摘录）。"""


async def collect_trait_evidence_llm(
    db: Session,
    *,
    user_id: str,
    ctx: EssayGradingContext,
    essay: str,
) -> dict[str, dict[str, Any]]:
    if not settings.trait_llm_evidence_enabled:
        return {}
    cred = get_credential(db, user_id, CredentialRole.primary)
    if not cred:
        return {}

    payload = {
        "prompt": ctx.prompt[:2000],
        "reference_material": (ctx.reference_material or "")[:2000],
        "user_essay": essay[:8000],
        "traits": [tid for tid in TRAIT_SPECS],
    }
    user_prompt = json.dumps(payload, ensure_ascii=False)
    raw, _usage = await chat_completion_json(cred, EVIDENCE_PROMPT, user_prompt)
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}

    out: dict[str, dict[str, Any]] = {}
    for row in data.get("traits") or []:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("trait_id") or "").strip().upper()
        if not tid.startswith("T"):
            continue
        out[tid] = {
            "evidence_positive": row.get("evidence_positive") or [],
            "evidence_negative": row.get("evidence_negative") or [],
            "evidence_missing": row.get("evidence_missing") or [],
        }
    return out
