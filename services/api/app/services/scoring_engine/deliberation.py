"""第 3 层：规则触发的审议（非完整多智能体，仅标记与边界提示）。"""

from __future__ import annotations

from app.domain.scoring_engine.level_config import LevelConfig
from app.domain.scoring_engine.types import DeterministicScoreResult


def should_trigger_deliberation(
    det: DeterministicScoreResult,
    level_config: LevelConfig,
) -> tuple[bool, str]:
    borderline = sum(1 for h in det.point_hits if h.status == "borderline")
    if borderline >= 2:
        return True, f"存在 {borderline} 个边界语义命中，建议 LLM 仲裁"

    dim = det.dimension_scores
    d01 = dim.get("D01", {}).get("score", 0)
    d02 = dim.get("D02", {}).get("score", 0)
    d03 = dim.get("D03", {}).get("score", 0)
    d04 = dim.get("D04", {}).get("score", 0)

    for trigger in level_config.deliberation_triggers:
        if "立意" in trigger and d01 < d02 * 0.6 and d02 > 0:
            return True, trigger
        if "对策" in trigger and level_config.level_id == "municipal" and d03 < d04 * 0.6 and d04 > 0:
            return True, trigger
        if "法治" in trigger and level_config.level_id == "enforcement" and d01 < d03 * 0.5:
            return True, trigger

    if not det.main_point_hit:
        return True, "总论点/扣题信号弱"
    return False, ""
