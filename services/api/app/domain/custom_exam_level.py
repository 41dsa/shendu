"""自备大作文批改：申论卷别层级（与 scoring_engine.level_config 对齐）。"""

from __future__ import annotations

from typing import Any

from app.domain.exam_catalog import normalize_exam_type, normalize_job_category
from app.domain.scoring_engine.level_config import ExamLevelId, LEVEL_CONFIGS

CUSTOM_EXAM_LEVEL_OPTIONS: list[dict[str, str]] = [
    {"value": "provincial", "label": "副省级 / 中央机关"},
    {"value": "municipal", "label": "市地级 / 县乡机关"},
    {"value": "enforcement", "label": "行政执法类"},
]

_VALID: frozenset[str] = frozenset(LEVEL_CONFIGS.keys())


def normalize_exam_level(raw: str | None) -> ExamLevelId | None:
    if raw is None:
        return None
    key = (raw or "").strip().lower()
    if key in _VALID:
        return key  # type: ignore[return-value]
    aliases = {
        "副省级": "provincial",
        "副省": "provincial",
        "中央机关": "provincial",
        "市地级": "municipal",
        "地市": "municipal",
        "县乡": "municipal",
        "执法": "enforcement",
        "行政执法": "enforcement",
    }
    for token, level in aliases.items():
        if token in (raw or ""):
            return level  # type: ignore[return-value]
    return None


def exam_level_from_profile(*, exam_type: str, job_category: str) -> ExamLevelId:
    """考试目标 job_category → 自备批改默认卷别。"""
    et = normalize_exam_type(exam_type)
    job = normalize_job_category(et, job_category)
    if job == "fusheng":
        return "provincial"
    if job == "zhifa":
        return "enforcement"
    if et == "shengkao" and job == "shiji":
        return "provincial"
    return "municipal"


def exam_level_display(level_id: str | None) -> str | None:
    if not level_id:
        return None
    cfg = LEVEL_CONFIGS.get(level_id)  # type: ignore[arg-type]
    return cfg.display_name if cfg else level_id


def custom_exam_level_form_options() -> list[dict[str, Any]]:
    return [{"value": o["value"], "label": o["label"]} for o in CUSTOM_EXAM_LEVEL_OPTIONS]
