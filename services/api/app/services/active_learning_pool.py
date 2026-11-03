"""PRD §8.3 主动学习难例池（V1 触发与入池）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.trait_definitions import level_to_numeric
from app.domain.scoring_engine.types import ScoringEngineResult
from app.models.entities import ActiveLearningPoolEntry, ActiveLearningReason


def _snapshot_from_result(result: ScoringEngineResult) -> dict[str, Any]:
    return {
        "trait_vote_max_spread": result.trait_vote_max_spread,
        "trait_confidence": result.trait_confidence,
        "ability_level": result.ability_level,
        "score_display_mode": result.score_display_mode,
        "traits": [
            {
                "trait_id": r.get("trait_id"),
                "level": r.get("level"),
                "vote_spread": r.get("vote_spread"),
                "evidence_insufficient": r.get("evidence_insufficient"),
            }
            for r in (result.trait_diagnostics or [])
        ],
    }


def compute_trait_retry_deltas(
    prior_traits: list[dict[str, Any]],
    current_traits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prior = {str(r.get("trait_id")): r for r in prior_traits}
    deltas: list[dict[str, Any]] = []
    for cur in current_traits:
        tid = str(cur.get("trait_id") or "")
        if not tid or tid not in prior:
            continue
        p_lv = prior[tid].get("level")
        c_lv = cur.get("level")
        if p_lv == c_lv:
            continue
        delta = level_to_numeric(c_lv) - level_to_numeric(p_lv) if c_lv and p_lv else 0
        deltas.append(
            {
                "trait_id": tid,
                "prior_level": p_lv,
                "current_level": c_lv,
                "delta_numeric": delta,
            }
        )
    return deltas


def evaluate_active_learning_triggers(
    result: ScoringEngineResult,
    *,
    standard_match_confidence: float,
) -> list[tuple[ActiveLearningReason, float]]:
    """纯函数：返回 (原因, 优先级) 列表。"""
    triggers: list[tuple[ActiveLearningReason, float]] = []
    spread = float(result.trait_vote_max_spread or 0)
    if spread >= settings.active_learning_vote_spread_threshold:
        triggers.append((ActiveLearningReason.trait_vote_spread, min(1.0, 0.5 + spread)))

    insufficient = sum(1 for r in (result.trait_diagnostics or []) if r.get("evidence_insufficient"))
    if insufficient >= 2:
        triggers.append((ActiveLearningReason.evidence_insufficient, 0.55 + insufficient * 0.05))

    if standard_match_confidence < settings.active_learning_standard_match_threshold:
        triggers.append((ActiveLearningReason.standard_match_low, 0.7))

    boundary = 0
    conf_max = float(settings.active_learning_boundary_confidence_max)
    for row in result.trait_diagnostics or []:
        lv = row.get("level")
        if not lv:
            continue
        n = level_to_numeric(lv)
        conf = float(row.get("confidence") or 0.75)
        if n in (1, 2, 3) and conf < conf_max:
            boundary += 1
    if boundary >= 2:
        triggers.append((ActiveLearningReason.level_boundary, 0.6))

    for row in result.trait_diagnostics or []:
        vs = row.get("vote_spread")
        if vs is not None and float(vs) >= 0.5:
            triggers.append((ActiveLearningReason.self_consistency, 0.65))
            break

    return triggers


def enqueue_active_learning(
    db: Session,
    *,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    result: ScoringEngineResult,
    standard_match_confidence: float,
) -> int:
    triggers = evaluate_active_learning_triggers(result, standard_match_confidence=standard_match_confidence)
    snap = _snapshot_from_result(result)
    count = 0
    for reason, priority in triggers:
        db.add(
            ActiveLearningPoolEntry(
                grading_job_id=grading_job_id,
                submission_id=submission_id,
                question_id=question_id,
                reason=reason,
                priority=round(priority, 3),
                status="open",
                snapshot=snap,
            )
        )
        count += 1
    return count


def enqueue_retry_trait_volatility(
    db: Session,
    *,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    prior_traits: list[dict[str, Any]],
    current_traits: list[dict[str, Any]],
) -> int:
    """AL-02：重作 Trait 档位波动入池（弱监督 retry_delta 并行）。"""
    deltas = compute_trait_retry_deltas(prior_traits, current_traits)
    major = [d for d in deltas if abs(int(d.get("delta_numeric") or 0)) >= 1]
    if len(major) < int(settings.active_learning_retry_min_level_changes):
        return 0
    db.add(
        ActiveLearningPoolEntry(
            grading_job_id=grading_job_id,
            submission_id=submission_id,
            question_id=question_id,
            reason=ActiveLearningReason.self_consistency,
            priority=0.68,
            status="open",
            snapshot={"retry_trait_delta": deltas, "major_changes": len(major)},
        )
    )
    return 1


def enqueue_dispute_sample(
    db: Session,
    *,
    report_id: str,
    submission_id: str | None,
    question_id: str | None,
    reason_text: str,
) -> None:
    db.add(
        ActiveLearningPoolEntry(
            submission_id=submission_id,
            question_id=question_id,
            reason=ActiveLearningReason.user_dispute,
            priority=0.85,
            status="open",
            snapshot={"report_id": report_id, "dispute_reason": reason_text[:500]},
        )
    )
