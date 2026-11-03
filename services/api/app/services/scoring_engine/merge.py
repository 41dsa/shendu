from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.types import ScoringEngineResult


def merge_engine_with_llm_payload(
    engine: ScoringEngineResult,
    llm_payload: dict[str, Any],
    *,
    max_llm_delta: float = 4.0,
    max_score: float = 40.0,
    grading_ctx: Any | None = None,
) -> dict[str, Any]:
    """V1：以 Trait 区间中心为唯一总分脊柱；LLM 总分仅作弱标签保留，不参与合并。"""
    payload = dict(llm_payload)
    llm_total = float(payload.get("total_score") or 0)
    if llm_total <= 0:
        from app.services.grading_helpers import resolved_primary_llm_score

        llm_total = resolved_primary_llm_score(payload) or 0.0

    trait_mode = bool(engine.trait_diagnostics)
    if trait_mode and engine.suppress_absolute_score:
        engine_total = 0.0
        final_total = 0.0
    elif trait_mode and engine.system_center_score is not None:
        engine_total = float(engine.system_center_score)
        final_total = engine_total
    else:
        engine_total = float(engine.total_score)
        final_total = engine_total

    payload["llm_total_discarded"] = True
    payload["engine_total_discarded"] = False
    payload["trait_score_spine"] = trait_mode
    payload["llm_weak_label_total"] = llm_total
    payload["llm_total_delta"] = round(abs(llm_total - final_total), 2) if llm_total else None

    payload["rule_score"] = engine_total
    payload["deterministic_score"] = engine_total
    payload["llm_raw_total"] = llm_total
    payload["primary_llm_score"] = llm_total
    payload["llm_score"] = llm_total
    payload["merged_total"] = final_total
    payload["total_score"] = final_total

    if trait_mode and engine.trait_diagnostics:
        from app.services.scoring_engine.report_adapter import trait_rows_as_scoring_points

        payload["scoring_points"] = trait_rows_as_scoring_points(
            engine.trait_diagnostics,
            max_score=max_score,
        )
    elif not payload.get("scoring_points"):
        payload["scoring_points"] = list(engine.dimension_rows)

    if engine.evidence_chain:
        payload["evidence_chain"] = list(engine.evidence_chain)

    from app.services.scoring_engine.orchestrator import engine_result_to_payload_meta

    meta = engine_result_to_payload_meta(engine)
    payload.update(meta)
    from app.domain.scoring_engine.score_display_policy import apply_score_display_to_payload

    display_mode = engine.score_display_mode or "center"
    if engine.suppress_absolute_score:
        display_mode = "tier_only"
    apply_score_display_to_payload(
        payload,
        score_display_mode=display_mode,  # type: ignore[arg-type]
        human_review=bool(engine.human_review_recommended) or engine.suppress_absolute_score,
        score_interval=engine.score_interval,
    )
    if engine.score_display_mode == "center" and not engine.suppress_absolute_score:
        payload["display_mode"] = "normal"
        payload["trait_low_confidence"] = False
        if engine.score_interval:
            payload["score_range"] = list(engine.score_interval)
    if engine.ability_level:
        payload["ability_level"] = engine.ability_level
    if engine.trait_dispute_notes:
        payload["trait_dispute_notes"] = list(engine.trait_dispute_notes)
    payload.setdefault("score_disclaimer", meta.get("score_disclaimer"))

    from app.services.grading_helpers import overlay_llm_dimension_reasons, resolve_review_notes_excerpt

    if not payload.get("trait_score_spine"):
        overlay_llm_dimension_reasons(payload)
    resolve_review_notes_excerpt(payload)

    if trait_mode:
        from app.services.scoring_engine.trait_report_builder import finalize_trait_v1_report

        if grading_ctx is not None:
            payload = finalize_trait_v1_report(payload, engine, grading_ctx, llm_snapshot=llm_payload)
    return payload
