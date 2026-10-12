"""五层评分引擎编排：闸门 → 级别适配 → 确定性评分 → 审议标记 → 校准 → 报告适配。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.calibration import apply_calibration_with_text
from app.domain.scoring_engine.input_gate import run_input_gate
from app.domain.scoring_engine.level_config import LEVEL_CONFIG_VERSION, ExamLevelId, get_level_config
from app.domain.scoring_engine.types import DeterministicScoreResult, EngineLayerTrace, ScoringEngineResult, ScoringPoint
from app.services.essay_context import EssayGradingContext, word_bounds_for_context
from app.services.scoring_engine.arbitration import arbitrate_borderline_hits
from app.services.scoring_engine.deliberation import should_trigger_deliberation
from app.services.scoring_engine.deliberation_mares import apply_deliberation_to_result, run_deliberation_mares
from app.services.scoring_engine.deterministic import run_deterministic_engine
from app.services.scoring_engine.level_resolver import resolve_exam_level
from app.services.scoring_engine.point_pool import POINT_POOL_VERSION, build_point_pool
from app.services.scoring_engine.pool_loader import atomic_points_to_scoring_points, load_point_pool_for_level
from app.domain.scoring_engine.similarity_provider import SimilarityProvider
from app.services.embedding_service import build_similarity_provider
from app.services.scoring_engine.recompute import recompute_from_hits
from app.services.scoring_engine.report_adapter import (
    dimension_rows_from_engine,
    evidence_chain_from_hits,
    point_hits_payload,
    tier_summary,
)


def _resolve_point_pool(
    ctx: EssayGradingContext,
    level_id: ExamLevelId,
    max_score: float,
) -> tuple[list[ScoringPoint], str, str]:
    if ctx.point_pools:
        pool = load_point_pool_for_level(
            {"point_pools": ctx.point_pools},
            level_id,
            question_id=ctx.question_id or None,
        )
        if pool and pool.points:
            return atomic_points_to_scoring_points(pool, level_id), pool.version, "published_point_pool"
    legacy = build_point_pool(
        rubric_criteria=ctx.rubric_criteria,
        scoring_dimensions=ctx.scoring_points,
        focus_points=ctx.focus_points,
        level_id=level_id,
        max_score=max_score,
    )
    return legacy, POINT_POOL_VERSION, "rubric_adapter"


def _finalize_result(
    ctx: EssayGradingContext,
    content: str,
    *,
    level_id: ExamLevelId,
    level_inferred: bool,
    level_config,
    det: DeterministicScoreResult,
    pool_version: str,
    pool_source: str,
    traces: list[EngineLayerTrace],
    gate_word_ratio: float,
    points: list[ScoringPoint],
) -> ScoringEngineResult:
    max_score = float(ctx.score)
    deliberation, note = should_trigger_deliberation(det, level_config)
    if deliberation:
        traces.append(EngineLayerTrace(layer="deliberation", detail="triggered", data={"note": note}))

    word_min, word_max = word_bounds_for_context(ctx)
    cal = apply_calibration_with_text(
        det.base_score,
        content,
        word_min=word_min,
        word_max=word_max,
        tier=det.tier,
        exam_level=level_id,
    )
    traces.extend(cal.traces)
    tier = cal.tier_adjusted or det.tier
    total = round(max(0.0, min(max_score, det.base_score + cal.total_penalty)), 1)

    return ScoringEngineResult(
        exam_level=level_id,
        level_inferred=level_inferred,
        level_config_version=LEVEL_CONFIG_VERSION,
        point_pool_version=pool_version,
        total_score=total,
        max_score=max_score,
        tier=tier,
        dimension_rows=dimension_rows_from_engine(det.dimension_scores, ctx.scoring_points),
        point_hits=det.point_hits,
        penalties=cal.penalties,
        confidence=_engine_confidence(det, deliberation, gate_word_ratio),
        level_specific_feedback=level_config.ability_focus_note,
        evidence_chain=evidence_chain_from_hits(det.point_hits, points=points),
        engine_traces=traces
        + [EngineLayerTrace(layer="point_pool", detail=pool_source, data={"version": pool_version})],
        deliberation_triggered=deliberation,
        deliberation_note=note,
        pool_points=list(points),
    )


def run_scoring_engine(
    ctx: EssayGradingContext,
    content: str,
    *,
    similarity_provider: SimilarityProvider | None = None,
) -> ScoringEngineResult | dict:
    return _run_scoring_engine_core(ctx, content, similarity_provider=similarity_provider)


def _run_scoring_engine_core(
    ctx: EssayGradingContext,
    content: str,
    *,
    similarity_provider: SimilarityProvider | None = None,
) -> ScoringEngineResult | dict:
    gate = run_input_gate(ctx, content)
    if not gate.passed and gate.short_circuit_payload:
        return gate.short_circuit_payload

    level_id, level_inferred = resolve_exam_level(ctx)
    max_score = float(ctx.score)
    level_config = get_level_config(level_id, max_score=max_score)
    traces: list[EngineLayerTrace] = [
        EngineLayerTrace(layer="input_gate", detail="passed", data={"word_ratio": gate.word_ratio}),
        EngineLayerTrace(
            layer="level_adapter",
            detail=level_id,
            data={"level_inferred": level_inferred, "config_version": LEVEL_CONFIG_VERSION},
        ),
    ]
    if similarity_provider:
        traces.append(
            EngineLayerTrace(
                layer="embedding",
                detail=similarity_provider.backend,
                data={"model": similarity_provider.model},
            )
        )

    pool, pool_version, pool_source = _resolve_point_pool(ctx, level_id, max_score)
    det = run_deterministic_engine(
        content,
        pool,
        level_config,
        max_score=max_score,
        scoring_dimensions=ctx.scoring_points,
        similarity_provider=similarity_provider,
    )
    traces.extend(det.traces)
    return _finalize_result(
        ctx,
        content,
        level_id=level_id,
        level_inferred=level_inferred,
        level_config=level_config,
        det=det,
        pool_version=pool_version,
        pool_source=pool_source,
        traces=traces,
        gate_word_ratio=gate.word_ratio,
        points=pool,
    )


async def run_scoring_engine_online(
    db: Session,
    ctx: EssayGradingContext,
    content: str,
    *,
    user_id: str,
    job_id: str,
    submission_id: str,
) -> ScoringEngineResult | dict:
    level_id_peek, _ = resolve_exam_level(ctx)
    max_score = float(ctx.score)
    pool, pool_version, pool_source = _resolve_point_pool(ctx, level_id_peek, max_score)
    similarity_provider = await build_similarity_provider(
        db,
        user_id=user_id,
        essay=content,
        points=pool,
    )
    base = _run_scoring_engine_core(ctx, content, similarity_provider=similarity_provider)
    if isinstance(base, dict):
        return base

    level_id = base.exam_level  # type: ignore[assignment]
    level_config = get_level_config(level_id, max_score=max_score)

    hits = await arbitrate_borderline_hits(
        db,
        user_id=user_id,
        job_id=job_id,
        essay=content,
        hits=base.point_hits,
        points=pool,
    )
    if hits != base.point_hits:
        det = recompute_from_hits(
            hits,
            pool,
            level_config,
            max_score=max_score,
            scoring_dimensions=ctx.scoring_points,
        )
        base = _finalize_result(
            ctx,
            content,
            level_id=level_id,
            level_inferred=base.level_inferred,
            level_config=level_config,
            det=det,
            pool_version=pool_version,
            pool_source=pool_source + "+arbitration",
            traces=list(base.engine_traces),
            gate_word_ratio=1.0,
            points=pool,
        )

    if base.deliberation_triggered:
        det_for_delib = recompute_from_hits(
            base.point_hits,
            pool,
            level_config,
            max_score=max_score,
            scoring_dimensions=ctx.scoring_points,
        )
        deliberation = await run_deliberation_mares(
            db,
            user_id=user_id,
            job_id=job_id,
            exam_level=level_id,
            essay_excerpt=content,
            det=det_for_delib,
            max_score=max_score,
        )
        base = apply_deliberation_to_result(base, deliberation)
        if deliberation:
            base.engine_traces.append(
                EngineLayerTrace(layer="deliberation", detail="mares", data=deliberation)
            )

    if settings.point_pool_pipeline_enabled:
        from app.services.scoring_engine.feedback_log import persist_point_hit_logs

        persist_point_hit_logs(
            db,
            grading_job_id=job_id,
            submission_id=submission_id,
            question_id=ctx.question_id or submission_id,
            result=base,
        )

    return base


def engine_result_to_payload_meta(result: ScoringEngineResult) -> dict:
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
        },
        "tier_label": tier_summary(result.tier),
        "level_specific_feedback": result.level_specific_feedback,
    }


def _engine_confidence(det: DeterministicScoreResult, deliberation: bool, word_ratio: float) -> float:
    if word_ratio < 0.5:
        return 0.55
    borderline = sum(1 for h in det.point_hits if h.status == "borderline")
    base = 0.82 - borderline * 0.04
    if deliberation:
        base -= 0.06
    return round(max(0.5, min(0.95, base)), 2)
