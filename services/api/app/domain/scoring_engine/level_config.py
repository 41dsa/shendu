from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExamLevelId = Literal["provincial", "municipal", "enforcement"]

LEVEL_CONFIG_VERSION = "1.0.0"


@dataclass(frozen=True)
class LevelConfig:
    level_id: ExamLevelId
    display_name: str
    dimension_weights: dict[str, float]
    matching_thresholds: dict[str, float]
    tier_rules: list[dict[str, Any]]
    ability_focus_note: str
    deliberation_triggers: list[str]


def _base_tiers(max_score: float) -> list[dict[str, Any]]:
    scale = max_score / 40.0
    return [
        {
            "tier_id": "t1",
            "label": f"一类文（{round(32 * scale)}—{round(40 * scale)}）",
            "score_min": 32 * scale,
            "score_max": 40 * scale,
            "main_required": True,
            "coverage_min": 0.8,
        },
        {
            "tier_id": "t2",
            "label": f"二类文（{round(24 * scale)}—{round(31 * scale)}）",
            "score_min": 24 * scale,
            "score_max": 31 * scale,
            "main_required": True,
            "coverage_min": 0.5,
        },
        {
            "tier_id": "t3",
            "label": f"三类文（{round(16 * scale)}—{round(23 * scale)}）",
            "score_min": 16 * scale,
            "score_max": 23 * scale,
            "main_required": False,
            "coverage_min": 0.0,
        },
        {
            "tier_id": "t4",
            "label": f"四类文（0—{round(15 * scale)}）",
            "score_min": 0,
            "score_max": 15 * scale,
            "main_required": False,
            "coverage_min": 0.0,
        },
    ]


def _cfg(
    level_id: ExamLevelId,
    display_name: str,
    dim_weights: dict[str, float],
    high: float,
    low: float,
    note: str,
    triggers: list[str],
    max_score: float = 40,
) -> LevelConfig:
    return LevelConfig(
        level_id=level_id,
        display_name=display_name,
        dimension_weights=dim_weights,
        matching_thresholds={"high": high, "low": low},
        tier_rules=_base_tiers(max_score),
        ability_focus_note=note,
        deliberation_triggers=triggers,
    )


LEVEL_CONFIGS: dict[ExamLevelId, LevelConfig] = {
    "provincial": _cfg(
        "provincial",
        "副省级",
        {
            "D01": 0.30,
            "D02": 0.15,
            "D03": 0.20,
            "D04": 0.10,
            "A1": 0.30,
            "A2": 0.15,
            "A3": 0.20,
            "A4": 0.10,
            "A5": 0.15,
        },
        high=0.62,
        low=0.42,
        note="副省级侧重立意高度、辩证分析与理论深度；建议从制度与宏观层面展开。",
        triggers=["立意维度弱但结构维度强", "总论点匹配置信度边界"],
    ),
    "municipal": _cfg(
        "municipal",
        "市地级",
        {
            "D01": 0.22,
            "D02": 0.15,
            "D03": 0.28,
            "D04": 0.10,
            "A1": 0.22,
            "A2": 0.15,
            "A3": 0.28,
            "A4": 0.10,
            "A5": 0.25,
        },
        high=0.58,
        low=0.38,
        note="市地级侧重对策可行性与贯彻执行；对策段宜具体、可落地。",
        triggers=["对策维度弱但语言维度强"],
    ),
    "enforcement": _cfg(
        "enforcement",
        "行政执法",
        {
            "D01": 0.25,
            "D02": 0.12,
            "D03": 0.25,
            "D04": 0.18,
            "A1": 0.25,
            "A2": 0.12,
            "A3": 0.25,
            "A4": 0.18,
            "A5": 0.20,
        },
        high=0.60,
        low=0.40,
        note="行政执法卷强调法治思维与规范表达；避免感性抒情，注意格式合规。",
        triggers=["法治相关维度弱但其他维度强"],
    ),
}


def get_level_config(level_id: ExamLevelId, *, max_score: float = 40) -> LevelConfig:
    base = LEVEL_CONFIGS[level_id]
    if max_score == 40:
        return base
    return _cfg(
        base.level_id,
        base.display_name,
        base.dimension_weights,
        base.matching_thresholds["high"],
        base.matching_thresholds["low"],
        base.ability_focus_note,
        base.deliberation_triggers,
        max_score=max_score,
    )
