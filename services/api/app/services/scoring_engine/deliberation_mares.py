"""第 3 层多智能体审议（MARES 简化：专家 × 级别 + 综合裁定）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.level_config import ExamLevelId, get_level_config
from app.domain.scoring_engine.types import DeterministicScoreResult, ScoringEngineResult
from app.models.entities import CredentialRole
from app.services.ai_client import AiCallError, chat_completion_json, get_credential


_LEVEL_EXPERTS: dict[ExamLevelId, list[str]] = {
    "provincial": ["立意高度与辩证深度", "理论运用恰当性", "宏观统筹意识"],
    "municipal": ["对策可行性与具体性", "基层场景贴合度", "贯彻执行逻辑"],
    "enforcement": ["法治思维体现", "公共服务导向", "格式规范与表达合规"],
}


async def run_deliberation_mares(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    exam_level: ExamLevelId,
    essay_excerpt: str,
    det: DeterministicScoreResult,
    max_score: float,
) -> dict[str, Any] | None:
    if not settings.scoring_deliberation_enabled:
        return None
    cred = get_credential(db, user_id, CredentialRole.primary)
    if not cred:
        return None

    experts = _LEVEL_EXPERTS.get(exam_level, _LEVEL_EXPERTS["municipal"])
    level_cfg = get_level_config(exam_level, max_score=max_score)
    expert_scores: list[float] = []

    context = {
        "dimension_scores": det.dimension_scores,
        "coverage_ratio": det.coverage_ratio,
        "main_point_hit": det.main_point_hit,
        "tier": det.tier.label,
    }
    for dim in experts:
        system = (
            f"你是申论{level_cfg.display_name}阅卷专家，只评「{dim}」。"
            f'输出 JSON：{{"score": number, "max": number, "confidence": number, "reason": string}}，max 建议 {max_score/3:.1f}'
        )
        user = json.dumps({"essay_excerpt": essay_excerpt[:3000], "context": context}, ensure_ascii=False)
        try:
            raw, _u = await chat_completion_json(cred, system, user)
            data = json.loads(raw)
            expert_scores.append(float(data.get("score") or 0))
        except (AiCallError, json.JSONDecodeError):
            expert_scores.append(det.base_score / 3)

    spread = max(expert_scores) - min(expert_scores) if expert_scores else 0.0
    synth_system = (
        "你是审议综合智能体。根据专家分数与差异，输出最终总分建议。"
        'JSON：{"total_score": number, "note": string}'
    )
    synth_user = json.dumps(
        {"expert_scores": expert_scores, "deterministic_total": det.base_score, "spread": spread},
        ensure_ascii=False,
    )
    try:
        raw, _u = await chat_completion_json(cred, synth_system, synth_user)
        data = json.loads(raw)
        suggested = float(data.get("total_score") or det.base_score)
    except (AiCallError, json.JSONDecodeError):
        suggested = det.base_score

    return {
        "experts": experts,
        "expert_scores": expert_scores,
        "spread": round(spread, 2),
        "suggested_total": round(suggested, 1),
        "note": "多智能体审议完成",
    }


def apply_deliberation_to_result(result: ScoringEngineResult, deliberation: dict[str, Any] | None) -> ScoringEngineResult:
    if not deliberation:
        return result
    suggested = float(deliberation.get("suggested_total") or result.total_score)
    delta = abs(suggested - result.total_score)
    if delta <= 2.5:
        result.total_score = round((result.total_score * 0.6 + suggested * 0.4), 1)
    result.deliberation_note = str(deliberation.get("note") or result.deliberation_note)
    result.deliberation_triggered = True
    return result
