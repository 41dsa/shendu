"""Trait 引擎综合置信度。"""

from __future__ import annotations

from app.domain.scoring_engine.trait_definitions import TraitDiagnostic, level_to_numeric


def compute_trait_engine_confidence(
    diagnostics: list[TraitDiagnostic],
    *,
    standard_match_confidence: float,
    word_ratio: float,
    model_vote_spread: float = 0.0,
    evidence_grounding_rate: float = 1.0,
) -> tuple[float, bool]:
    if word_ratio < 0.5:
        return 0.52, True
    if standard_match_confidence < 0.6:
        return 0.56, True

    low_evidence = sum(
        1
        for d in diagnostics
        if d.participates_in_score
        and len(d.evidence.positive) + len(d.evidence.negative) == 0
    )
    levels = [d.level for d in diagnostics if d.participates_in_score and d.level]
    boundary = False
    if levels:
        nums = [level_to_numeric(lv) for lv in levels if lv]
        if nums and max(nums) - min(nums) >= 3:
            boundary = True

    grounding_penalty = 0.0 if evidence_grounding_rate >= 0.85 else (0.85 - evidence_grounding_rate) * 0.35
    base = (
        0.78
        + standard_match_confidence * 0.08
        - low_evidence * 0.06
        - model_vote_spread * 0.12
        - grounding_penalty
    )
    if boundary:
        base -= 0.07
    conf = round(max(0.45, min(0.92, base)), 2)
    suppress = conf < 0.58 or standard_match_confidence < 0.55
    return conf, suppress
