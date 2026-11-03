"""PRD V1 诊断标准执行器编排（Trait 引擎为批改唯一脊柱；采分点池仅标准生产遗留）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.essay_grading_context import EssayGradingContext
from app.domain.scoring_engine.input_gate import run_input_gate
from app.domain.scoring_engine.level_config import LEVEL_CONFIG_VERSION
from app.domain.scoring_engine.types import EngineLayerTrace, ScoringEngineResult
from app.domain.scoring_engine.v1_engine import build_engine_result
from app.services.scoring_engine.level_resolver import resolve_exam_level

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
from app.services.scoring_engine.report_adapter import point_hits_payload, tier_summary


def run_scoring_engine(
    ctx: EssayGradingContext,
    content: str,
    **_,
) -> ScoringEngineResult | dict:
    gate = run_input_gate(ctx, content)
    if not gate.passed and gate.short_circuit_payload:
        return gate.short_circuit_payload

    level_id, level_inferred = resolve_exam_level(ctx)
    from app.domain.scoring_engine.types import EngineLayerTrace

    traces = [
        EngineLayerTrace(layer="input_gate", detail="passed", data={"word_ratio": gate.word_ratio}),
        EngineLayerTrace(
            layer="exam_context",
            detail=level_id,
            data={"level_inferred": level_inferred, "config_version": LEVEL_CONFIG_VERSION},
        ),
    ]
    return build_engine_result(
        ctx,
        content,
        exam_level=level_id,
        level_inferred=level_inferred,
        word_ratio=gate.word_ratio,
        traces=traces,
    )


async def run_scoring_engine_online(
    db: "Session",
    ctx: EssayGradingContext,
    content: str,
    *,
    user_id: str,
    job_id: str,
    submission_id: str,
    persist_hit_logs: bool = True,
) -> ScoringEngineResult | dict:
    from app.config import settings
    from app.domain.scoring_engine.input_gate import run_input_gate
    from app.domain.scoring_engine.rebuild_result import (
        rebuild_engine_after_llm_evidence,
        rebuild_engine_after_trait_votes,
    )
    from app.domain.scoring_engine.trait_vote_merge import apply_vote_levels
    from app.services.scoring_engine.trait_evidence_llm import collect_trait_evidence_llm
    from app.services.scoring_engine.trait_voting import collect_trait_votes
    from app.services.scoring_engine.level_resolver import resolve_exam_level

    from app.services.anchor_scale_service import (
        count_published_anchors,
        essay_trait_levels_from_diagnostics,
        nearest_anchor_match,
    )

    from app.domain.scoring_engine.question_standard_card import build_question_standard_card

    standard_card = build_question_standard_card(ctx)
    std_match_confidence = float(standard_card.match_confidence)

    if ctx.question_id:
        ctx.anchor_count = count_published_anchors(db, ctx.question_id)

    result = run_scoring_engine(ctx, content)
    if isinstance(result, dict):
        return result

    gate = run_input_gate(ctx, content)
    level_id, level_inferred = resolve_exam_level(ctx)

    if settings.trait_llm_evidence_enabled:
        llm_evidence = await collect_trait_evidence_llm(
            db,
            user_id=user_id,
            ctx=ctx,
            essay=content,
        )
        if llm_evidence:
            result = rebuild_engine_after_llm_evidence(
                ctx,
                content,
                result,
                llm_evidence,
                word_ratio=gate.word_ratio,
                exam_level=level_id,
                level_inferred=level_inferred,
            )

    if settings.trait_llm_voting_enabled and result.trait_diagnostics:
        vote_map, max_spread, vote_evidence = await collect_trait_votes(
            db,
            user_id=user_id,
            ctx=ctx,
            essay=content,
            base_diagnostics=result.trait_diagnostics,
        )
        if vote_evidence:
            result = rebuild_engine_after_llm_evidence(
                ctx,
                content,
                result,
                vote_evidence,
                word_ratio=gate.word_ratio,
                exam_level=level_id,
                level_inferred=level_inferred,
            )
            result.engine_traces.append(
                EngineLayerTrace(
                    layer="evidence_llm",
                    detail="vote_models_merged",
                    data={"traits": len(vote_evidence)},
                )
            )
        if vote_map:
            rows = apply_vote_levels(result.trait_diagnostics, vote_map)

            result = rebuild_engine_after_trait_votes(
                result,
                rows,
                standard_match_confidence=std_match_confidence,
                word_ratio=gate.word_ratio,
                vote_max_spread=max_spread,
                severe_off_topic=bool(result.hard_rule_flags.get("severe_off_topic")),
                standard=standard_card,
            )
            result.engine_traces.append(
                EngineLayerTrace(
                    layer="trait_voting",
                    detail="merged",
                    data={"max_spread": max_spread, "traits": len(vote_map)},
                )
            )

    if persist_hit_logs:
        from app.config import settings
        from app.services.scoring_engine.feedback_log import persist_trait_scoring_records

        persist_trait_scoring_records(
            db,
            grading_job_id=job_id,
            submission_id=submission_id,
            question_id=ctx.question_id or submission_id,
            result=result,
        )
        if settings.weak_supervision_enabled and result.trait_diagnostics:
            from app.services.active_learning_pool import enqueue_active_learning

            try:
                enqueue_active_learning(
                    db,
                    grading_job_id=job_id,
                    submission_id=submission_id,
                    question_id=ctx.question_id or submission_id,
                    result=result,
                    standard_match_confidence=std_match_confidence,
                )
                db.commit()
            except Exception:
                db.rollback()

    if ctx.question_id and result.trait_diagnostics:
        rel = nearest_anchor_match(
            db,
            question_id=ctx.question_id,
            essay_trait_levels=essay_trait_levels_from_diagnostics(result.trait_diagnostics),
        )
        if rel:
            result.anchor_relative_scale = rel
            result.anchor_count = int(rel.get("anchor_count") or result.anchor_count)
            result.diagnostic_header = {
                **(result.diagnostic_header or {}),
                "anchor_relative_scale": rel,
            }
    result.standard_match_confidence = std_match_confidence
    if result.diagnostic_header is not None:
        result.diagnostic_header = {
            **result.diagnostic_header,
            "standard_match_confidence": std_match_confidence,
        }
    return result


def engine_result_to_payload_meta(result: ScoringEngineResult) -> dict:
    trait_block = {
        "engine": "diagnostic_trait_v1",
        "trait_engine_version": "v1",
        "rubric_version": result.rubric_version,
        "question_standard_version": result.question_standard_version,
        "standard_match_confidence": result.standard_match_confidence,
        "trait_diagnostics": result.trait_diagnostics,
        "ability_level": result.ability_level,
        "score_interval": list(result.score_interval) if result.score_interval else None,
        "system_center_score": result.system_center_score,
        "score_uncalibrated": result.score_uncalibrated,
        "trait_confidence": result.trait_confidence,
        "suppress_absolute_score": result.suppress_absolute_score,
        "trait_dispute_notes": result.trait_dispute_notes,
        "hard_rule_flags": result.hard_rule_flags,
        "primary_loss_traits": result.primary_loss_traits,
        "diagnostic_header": result.diagnostic_header,
        "multi_standard_views": result.multi_standard_views,
        "score_display_mode": result.score_display_mode,
        "human_review_recommended": result.human_review_recommended,
        "trait_vote_max_spread": result.trait_vote_max_spread,
        "anchor_count": result.anchor_count,
        "anchor_relative_scale": result.anchor_relative_scale or None,
        "score_disclaimer": None,  # finalize_trait_v1_report 写入 PRD 文案
    }
    return {
        "scoring_engine": {
            "exam_level": result.exam_level,
            "level_inferred": result.level_inferred,
            "level_config_version": result.level_config_version,
            "point_pool_version": result.point_pool_version,
            "tier": {
                "id": result.tier.tier_id,
                "label": result.tier.label,
                "reason": result.tier.reason,
            },
            "point_hits": point_hits_payload(result.point_hits, result.pool_points or None),
            "penalties": result.penalties,
            "deliberation_triggered": result.deliberation_triggered,
            "deliberation_note": result.deliberation_note,
            "layers": [{"layer": t.layer, "detail": t.detail, "data": t.data} for t in result.engine_traces],
            **trait_block,
        },
        "tier_label": tier_summary(result.tier),
        "level_specific_feedback": result.level_specific_feedback,
        "ability_level": result.ability_level,
        "trait_diagnostics": result.trait_diagnostics,
        "score_disclaimer": trait_block["score_disclaimer"],
        "diagnostic_header": result.diagnostic_header,
        "multi_standard_views": result.multi_standard_views,
        "score_display_mode": result.score_display_mode,
        "human_review_recommended": result.human_review_recommended,
    }
