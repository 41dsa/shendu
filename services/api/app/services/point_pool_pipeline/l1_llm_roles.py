from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import UserProviderCredential
from app.schemas.point_pool import ExamLevelId
from app.services.ai_client import AiCallError, chat_completion_json
from app.services.point_pool_pipeline.l1_candidates import llm_role_prompts


async def extract_llm_role_candidates(
    db: Session,
    cred: UserProviderCredential,
    *,
    prompt: str,
    material_excerpt: str,
    level_id: ExamLevelId,
    user_id: str,
    job_id: str,
) -> list[dict[str, Any]]:
    """L1 策略 C：多角色零样本采分点提取。"""
    out: list[dict[str, Any]] = []
    for role in llm_role_prompts(level_id):
        system = (
            f"你是{role['label']}。{role['hint']} "
            '仅输出 JSON：{"points":[{"text":string,"keywords":[string],"point_type":"main"|"sub"|"evidence"}]}'
        )
        user = json.dumps(
            {"prompt": prompt[:1500], "material": material_excerpt[:4000], "role": role["role"]},
            ensure_ascii=False,
        )
        try:
            raw, _usage = await chat_completion_json(cred, system, user)
            data = json.loads(raw)
            for p in data.get("points") or []:
                text = str(p.get("text") or "").strip()
                if len(text) < 4:
                    continue
                out.append(
                    {
                        "text": text,
                        "keywords": list(p.get("keywords") or []),
                        "source_para": [],
                        "extraction_method": f"llm_role_{role['role']}",
                        "point_type": p.get("point_type") or "sub",
                        "level_focus": role["hint"],
                    }
                )
        except (AiCallError, json.JSONDecodeError):
            continue
    return out
