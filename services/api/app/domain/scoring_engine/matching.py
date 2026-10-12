from __future__ import annotations

from app.domain.scoring_engine.text_utils import best_paragraph_match, keyword_hit, split_paragraphs
from app.domain.scoring_engine.types import MatchStage, PointHit, PointStatus, ScoringPoint
from app.domain.scoring_engine.level_config import LevelConfig
from app.domain.scoring_engine.similarity_provider import SimilarityProvider
from app.domain.scoring_engine.embedding import semantic_similarity


def match_scoring_point(
    essay: str,
    point: ScoringPoint,
    level_config: LevelConfig,
    *,
    similarity_provider: SimilarityProvider | None = None,
) -> PointHit:
    phrases = [point.text, *point.semantic_variants, *point.keywords]
    phrases = [p for p in phrases if p and p.strip()]
    sim_fn = (
        (lambda a, b: similarity_provider.similarity(a, b))
        if similarity_provider
        else None
    )
    para_idx, para_text, sim = best_paragraph_match(essay, phrases, similarity_fn=sim_fn)
    high = level_config.matching_thresholds["high"]
    low = level_config.matching_thresholds["low"]

    kw = keyword_hit(essay, point.keywords) or keyword_hit(essay, [point.text])
    stage: MatchStage = "miss"
    status: PointStatus = "missed"
    earned_ratio = 0.0

    if kw:
        stage = "keyword"
        status = "hit"
        earned_ratio = 1.0
    embed_sim = _max_embedding_similarity(essay, phrases, similarity_provider)
    sim = max(sim, embed_sim)
    if sim >= high:
        stage = "semantic"
        status = "hit"
        earned_ratio = 0.95
    elif sim >= low:
        stage = "borderline"
        status = "borderline"
        earned_ratio = 0.55
    else:
        stage = "miss"
        status = "missed"
        earned_ratio = 0.0

    if point.usage_band == "low":
        status = "advisory" if earned_ratio > 0 else "missed"
        earned_ratio *= 0.35

    max_score = float(point.max_score or point.weight or 1.0)
    earned = round(min(max_score, max_score * earned_ratio), 2)
    evidence = para_text[:240] if para_text else ""
    reason = ""
    if status == "hit":
        reason = "语义/关键词覆盖该采分单元"
    elif status == "borderline":
        reason = "语义接近但未完全覆盖，建议人工或 LLM 复核"
    elif status == "advisory":
        reason = "低置信准则，仅作建议参考"
    else:
        reason = "未在作答中发现足够证据"

    return PointHit(
        point_id=point.point_id,
        status=status,
        match_stage=stage,
        weight=point.weight,
        earned=earned,
        max_score=max_score,
        evidence=evidence,
        evidence_para=para_idx or None,
        reason=reason,
        suggestion="" if status in ("hit", "advisory") else "可对照材料与题干补写相关论述",
    )


def _max_embedding_similarity(
    essay: str,
    phrases: list[str],
    similarity_provider: SimilarityProvider | None,
) -> float:
    best = 0.0
    for para in split_paragraphs(essay):
        for phrase in phrases:
            if not phrase:
                continue
            if similarity_provider:
                best = max(best, similarity_provider.similarity(para, phrase))
            else:
                best = max(best, semantic_similarity(para, phrase))
    return best


def apply_arbitration_to_hit(hit: PointHit, *, accepted: bool, reason: str) -> PointHit:
    if not accepted:
        return PointHit(
            point_id=hit.point_id,
            status="missed",
            match_stage=hit.match_stage,
            weight=hit.weight,
            earned=0.0,
            max_score=hit.max_score,
            evidence=hit.evidence,
            evidence_para=hit.evidence_para,
            reason=reason,
            suggestion=hit.suggestion or "可补充相关论述",
        )
    earned = hit.max_score * 0.92
    return PointHit(
        point_id=hit.point_id,
        status="hit",
        match_stage="semantic",
        weight=hit.weight,
        earned=round(earned, 2),
        max_score=hit.max_score,
        evidence=hit.evidence,
        evidence_para=hit.evidence_para,
        reason=reason,
        suggestion="",
    )
