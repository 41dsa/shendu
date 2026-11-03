"""PRD V1 诊断与提分教练 · 标准执行器（完全替代采分点池引擎）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.config import settings
from app.domain.scoring_engine.level_config import LEVEL_CONFIG_VERSION
from app.domain.scoring_engine.multi_standard_views import build_multi_standard_views
from app.domain.scoring_engine.score_display_policy import (
    human_review_recommended,
    resolve_score_display_mode,
)
from app.domain.scoring_engine.rubric_engine import RUBRIC_VERSION
from app.domain.scoring_engine.question_standard_card import build_question_standard_card
from app.domain.scoring_engine.trait_pipeline import (
    evidence_meta_from_result,
    run_trait_pipeline,
    trait_diagnostics_to_payload,
)
from app.domain.scoring_engine.types import EngineLayerTrace, ScoringEngineResult, ScoringTier
from app.domain.essay_grading_context import word_bounds_for_context
from app.services.scoring_engine.report_adapter import (
    evidence_chain_from_traits,
    trait_rows_as_scoring_points,
    tier_from_ability,
)

if TYPE_CHECKING:
    from app.domain.essay_grading_context import EssayGradingContext


def build_engine_result(
    ctx: "EssayGradingContext",
    content: str,
    *,
    exam_level: str,
    level_inferred: bool,
    word_ratio: float,
    traces: list[EngineLayerTrace],
    model_vote_spread: float = 0.0,
    llm_evidence_by_trait: dict[str, dict] | None = None,
) -> ScoringEngineResult:
    max_score = float(ctx.score)
    word_min, word_max = word_bounds_for_context(ctx)

    standard = build_question_standard_card(ctx)
    force_diag = not standard.reviewed
    trait_out = run_trait_pipeline(
        content,
        standard,
        word_min=word_min,
        word_max=word_max,
        reference_material=ctx.reference_material or "",
        max_score=max_score,
        word_ratio=word_ratio,
        force_diagnostic_only=force_diag,
        model_vote_spread=model_vote_spread,
        llm_evidence_by_trait=llm_evidence_by_trait,
    )
    traces.extend(trait_out.traces)

    suppress = trait_out.suppress_absolute_score
    center = trait_out.interval.system_center
    severe = bool(trait_out.hard_rules.severe_off_topic or trait_out.signals.off_topic_signal)
    multi_views = build_multi_standard_views(
        trait_out.diagnostics,
        max_score=max_score,
        severe_off_topic=severe,
        standard=standard,
        baseline=trait_out.interval,
    )
    score_mode = resolve_score_display_mode(
        suppress_absolute_score=suppress,
        trait_confidence=trait_out.confidence,
        score_uncalibrated=trait_out.interval.uncalibrated,
        anchor_count=int(ctx.anchor_count if ctx.anchor_count is not None else settings.trait_anchor_count),
        diagnostic_only_mode=settings.diagnostic_only_mode,
        trait_vote_max_spread=model_vote_spread,
    )
    review = human_review_recommended(
        score_display_mode=score_mode,
        trait_confidence=trait_out.confidence,
        trait_vote_max_spread=model_vote_spread,
    )
    if suppress or score_mode in ("tier_only", "interval"):
        total = 0.0
    else:
        total = center
    tier = tier_from_ability(trait_out.interval.ability_level, max_score)

    trait_payload = trait_diagnostics_to_payload(
        trait_out.diagnostics,
        evidence_meta=evidence_meta_from_result(trait_out.evidence),
    )
    dimension_rows = trait_rows_as_scoring_points(trait_payload, max_score=max_score)
    evidence_chain = evidence_chain_from_traits(trait_payload)

    return ScoringEngineResult(
        exam_level=exam_level,
        level_inferred=level_inferred,
        level_config_version=LEVEL_CONFIG_VERSION,
        point_pool_version=RUBRIC_VERSION,
        total_score=total,
        max_score=max_score,
        tier=tier,
        dimension_rows=dimension_rows,
        point_hits=[],
        penalties={},
        confidence=trait_out.confidence,
        level_specific_feedback="",
        evidence_chain=evidence_chain,
        engine_traces=traces,
        deliberation_triggered=False,
        deliberation_note="",
        pool_points=[],
        trait_diagnostics=trait_payload,
        ability_level=trait_out.interval.ability_level,
        score_interval=(trait_out.interval.score_min, trait_out.interval.score_max),
        system_center_score=center,
        score_uncalibrated=trait_out.interval.uncalibrated,
        trait_confidence=trait_out.confidence,
        suppress_absolute_score=suppress,
        trait_dispute_notes=trait_out.dispute_notes,
        hard_rule_flags=dict(trait_out.hard_rules.flags),
        rubric_version=RUBRIC_VERSION,
        question_standard_version=standard.version,
        standard_match_confidence=float(standard.match_confidence),
        primary_loss_traits=trait_out.interval.primary_loss_traits,
        diagnostic_header={
            "q1_task": ctx.prompt[:500] if ctx.prompt else "",
            "q2_met": [x for x in trait_out.signals.keyword_hits[:6]],
            "q5_loss_sources": trait_out.interval.primary_loss_traits,
            "q6_disputes": list(
                dict.fromkeys(list(standard.dispute_marks or []) + trait_out.dispute_notes[:5])
            )[:8],
            "trait_vote_spread": model_vote_spread,
            "standard_match_confidence": float(standard.match_confidence),
        },
        multi_standard_views=multi_views,
        score_display_mode=score_mode,
        human_review_recommended=review,
        trait_vote_max_spread=model_vote_spread,
        anchor_count=int(ctx.anchor_count if ctx.anchor_count is not None else settings.trait_anchor_count),
        anchor_relative_scale={},
    )
