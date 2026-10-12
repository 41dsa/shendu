from __future__ import annotations

import re

from app.domain.scoring_engine.tiers import ScoringTier
from app.domain.scoring_engine.types import CalibrationResult, EngineLayerTrace


def _count_likely_typos(text: str) -> int:
    """轻量错别字代理：连续非常用字符或重复字。"""
    suspicious = re.findall(r"(.)\1{3,}", text)
    odd = re.findall(r"[^\u4e00-\u9fff\w，。；：、！？\n\r\s]{2,}", text)
    return len(suspicious) + len(odd)


def apply_calibration(
    total_score: float,
    *,
    word_count: int,
    word_min: int,
    word_max: int,
    tier: ScoringTier,
    exam_level: str,
    paragraph_count: int,
) -> CalibrationResult:
    penalties: dict[str, float] = {"typos": 0.0, "word_count": 0.0, "format": 0.0}
    traces: list[EngineLayerTrace] = []
    tier_adjusted: ScoringTier | None = None

    ratio = word_count / max(word_min, 1)
    if ratio < 0.8:
        penalties["word_count"] = -2.0 if ratio >= 0.6 else -4.0
        traces.append(
            EngineLayerTrace(
                layer="calibration",
                detail="word_count_penalty",
                data={"word_ratio": round(ratio, 3)},
            )
        )
        if ratio < 0.6 and tier.tier_id in ("t1", "t2"):
            tier_adjusted = ScoringTier(
                tier_id="t3",
                label=tier.label.replace("一类", "三类").replace("二类", "三类"),
                score_min=tier.score_min,
                score_max=tier.score_max,
                reason="字数低于建议 80%，降档处理",
            )

    if paragraph_count < 3:
        penalties["format"] = -1.0
        traces.append(EngineLayerTrace(layer="calibration", detail="structure_format", data={}))

    total_penalty = sum(penalties.values())
    return CalibrationResult(
        penalties=penalties,
        tier_adjusted=tier_adjusted,
        total_penalty=total_penalty,
        traces=traces,
    )


def apply_calibration_with_text(
    total_score: float,
    essay_text: str,
    *,
    word_min: int,
    word_max: int,
    tier: ScoringTier,
    exam_level: str,
) -> CalibrationResult:
    from app.domain.scoring_engine.text_utils import split_paragraphs

    paragraphs = split_paragraphs(essay_text)
    result = apply_calibration(
        total_score,
        word_count=len(essay_text.strip()),
        word_min=word_min,
        word_max=word_max,
        tier=tier,
        exam_level=exam_level,
        paragraph_count=len(paragraphs),
    )
    typo_n = _count_likely_typos(essay_text)
    if typo_n >= 3:
        result.penalties["typos"] = -min(3.0, typo_n // 3)
    return result
