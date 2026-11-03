"""Trait 投票后重算区间与结果字段。"""

from __future__ import annotations

from app.config import settings
from app.domain.scoring_engine.multi_standard_views import build_multi_standard_views
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard
from app.domain.scoring_engine.score_display_policy import (
    human_review_recommended,
    resolve_score_display_mode,
)
from app.domain.scoring_engine.trait_definitions import TraitDiagnostic, TraitEvidence
from app.domain.scoring_engine.trait_interval import estimate_score_interval
from app.domain.scoring_engine.trait_confidence import compute_trait_engine_confidence
from app.domain.scoring_engine.types import EngineLayerTrace, ScoringEngineResult
from app.domain.scoring_engine.v1_engine import build_engine_result
from app.domain.essay_grading_context import EssayGradingContext
from app.services.scoring_engine.report_adapter import (
    evidence_chain_from_traits,
    tier_from_ability,
    trait_rows_as_scoring_points,
)


def _row_to_diagnostic(row: dict) -> TraitDiagnostic:
    return TraitDiagnostic(
        trait_id=row["trait_id"],  # type: ignore[arg-type]
        name=str(row.get("name") or row["trait_id"]),
        standard_tier=(row.get("standard_tier") or "B"),  # type: ignore[arg-type]
        level=row.get("level"),  # type: ignore[arg-type]
        participates_in_score=bool(row.get("participates_in_score")),
        confidence=float(row.get("confidence") or 0.75),
        evidence=TraitEvidence(
            positive=list(row.get("evidence_positive") or []),
            negative=list(row.get("evidence_negative") or []),
            missing=list(row.get("evidence_missing") or []),
        ),
        conclusion=str(row.get("conclusion") or ""),
        dispute_hint=str(row.get("dispute_hint") or ""),
    )


def _mean_trait_grounding(trait_rows: list[dict]) -> float:
    rates = [float(r["evidence_grounding_rate"]) for r in trait_rows if r.get("evidence_grounding_rate") is not None]
    return sum(rates) / len(rates) if rates else 1.0


def rebuild_engine_after_llm_evidence(
    ctx: EssayGradingContext,
    content: str,
    result: ScoringEngineResult,
    llm_by_trait: dict[str, dict],
    *,
    word_ratio: float,
    exam_level: str,
    level_inferred: bool,
) -> ScoringEngineResult:
    traces = list(result.engine_traces)
    rebuilt = build_engine_result(
        ctx,
        content,
        exam_level=exam_level,
        level_inferred=level_inferred,
        word_ratio=word_ratio,
        traces=traces,
        llm_evidence_by_trait=llm_by_trait,
    )
    rebuilt.engine_traces.append(
        EngineLayerTrace(
            layer="evidence_llm",
            detail="merged",
            data={"traits": len(llm_by_trait)},
        )
    )
    return rebuilt


def rebuild_engine_after_trait_votes(
    result: ScoringEngineResult,
    trait_rows: list[dict],
    *,
    standard_match_confidence: float,
    word_ratio: float,
    vote_max_spread: float,
    severe_off_topic: bool,
    standard: QuestionStandardCard | None = None,
) -> ScoringEngineResult:
    diagnostics = [_row_to_diagnostic(r) for r in trait_rows]
    interval = estimate_score_interval(
        diagnostics,
        max_score=result.max_score,
        severe_off_topic=severe_off_topic,
        standard=standard,
    )
    conf, suppress = compute_trait_engine_confidence(
        diagnostics,
        standard_match_confidence=standard_match_confidence,
        word_ratio=word_ratio,
        model_vote_spread=vote_max_spread,
        evidence_grounding_rate=_mean_trait_grounding(trait_rows),
    )
    if result.suppress_absolute_score:
        suppress = True

    multi_views = build_multi_standard_views(
        diagnostics,
        max_score=result.max_score,
        severe_off_topic=severe_off_topic,
        standard=standard,
        baseline=interval,
    )
    score_mode = resolve_score_display_mode(
        suppress_absolute_score=suppress,
        trait_confidence=conf,
        score_uncalibrated=interval.uncalibrated,
        anchor_count=int(result.anchor_count or settings.trait_anchor_count),
        diagnostic_only_mode=settings.diagnostic_only_mode,
        trait_vote_max_spread=vote_max_spread,
    )
    review = human_review_recommended(
        score_display_mode=score_mode,
        trait_confidence=conf,
        trait_vote_max_spread=vote_max_spread,
    )
    if suppress or score_mode in ("tier_only", "interval"):
        total = 0.0
    else:
        total = interval.system_center
    tier = tier_from_ability(interval.ability_level, result.max_score)
    dimension_rows = trait_rows_as_scoring_points(trait_rows, max_score=result.max_score)

    return ScoringEngineResult(
        exam_level=result.exam_level,
        level_inferred=result.level_inferred,
        level_config_version=result.level_config_version,
        point_pool_version=result.point_pool_version,
        total_score=total,
        max_score=result.max_score,
        tier=tier,
        dimension_rows=dimension_rows,
        point_hits=[],
        penalties=result.penalties,
        confidence=conf,
        level_specific_feedback=result.level_specific_feedback,
        evidence_chain=evidence_chain_from_traits(trait_rows),
        engine_traces=result.engine_traces,
        deliberation_triggered=result.deliberation_triggered,
        deliberation_note=result.deliberation_note,
        pool_points=[],
        trait_diagnostics=trait_rows,
        ability_level=interval.ability_level,
        score_interval=(interval.score_min, interval.score_max),
        system_center_score=interval.system_center,
        score_uncalibrated=interval.uncalibrated,
        trait_confidence=conf,
        suppress_absolute_score=suppress,
        trait_dispute_notes=result.trait_dispute_notes,
        hard_rule_flags=result.hard_rule_flags,
        rubric_version=result.rubric_version,
        question_standard_version=result.question_standard_version,
        primary_loss_traits=interval.primary_loss_traits,
        diagnostic_header={
            **(result.diagnostic_header or {}),
            "q5_loss_sources": interval.primary_loss_traits,
            "trait_vote_spread": vote_max_spread,
        },
        multi_standard_views=multi_views,
        score_display_mode=score_mode,
        human_review_recommended=review,
        trait_vote_max_spread=vote_max_spread,
        anchor_count=result.anchor_count,
        anchor_relative_scale=dict(result.anchor_relative_scale or {}),
    )
