from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.types import ScoringEngineResult


def merge_engine_with_llm_payload(
    engine: ScoringEngineResult,
    llm_payload: dict[str, Any],
    *,
    max_llm_delta: float = 4.0,
    max_score: float = 40.0,
) -> dict[str, Any]:
    """以确定性引擎总分为脊柱，融合 LLM 维度反馈与 evidence 链。"""
    payload = dict(llm_payload)
    engine_total = float(engine.total_score)
    llm_total = float(payload.get("total_score") or engine_total)
    delta = abs(llm_total - engine_total)
    engine_unreliable = engine_total <= max_score * 0.08 and llm_total >= max_score * 0.2

    if delta > max_llm_delta:
        if engine_unreliable:
            final_total = llm_total
            payload["llm_total_discarded"] = False
            payload["engine_total_discarded"] = True
        else:
            final_total = engine_total
            payload["llm_total_discarded"] = True
            payload["engine_total_discarded"] = False
        payload["llm_total_delta"] = round(delta, 2)
    else:
        final_total = round(engine_total * 0.75 + llm_total * 0.25, 1)
        payload["llm_total_discarded"] = False
        payload["engine_total_discarded"] = False
        payload["llm_total_delta"] = round(delta, 2)

    payload["rule_score"] = engine_total
    payload["deterministic_score"] = engine_total
    payload["llm_raw_total"] = llm_total
    payload["primary_llm_score"] = llm_total
    payload["llm_score"] = llm_total
    payload["merged_total"] = final_total
    payload["total_score"] = final_total

    if not payload.get("scoring_points"):
        payload["scoring_points"] = list(engine.dimension_rows)

    if engine.evidence_chain:
        payload["evidence_chain"] = list(engine.evidence_chain)

    from app.services.scoring_engine.orchestrator import engine_result_to_payload_meta

    meta = engine_result_to_payload_meta(engine)
    payload.update(meta)
    tier_label = meta.get("tier_label")
    if tier_label:
        payload.setdefault("engine_tier_note", tier_label)

    from app.services.grading_helpers import resolve_review_notes_excerpt

    resolve_review_notes_excerpt(payload)

    return payload
