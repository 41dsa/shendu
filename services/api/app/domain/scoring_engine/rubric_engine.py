"""PRD ③ Rubric 引擎：Trait 等级描述与权重（配置见 data/rubric/trait_rubric_v1.json）。"""

from __future__ import annotations

import re

from app.domain.scoring_engine.evidence_engine import TraitEvidenceBundle
from app.domain.scoring_engine.rubric_loader import (
    assert_rubric_complete,
    load_trait_rubric_document,
    merged_scorable_weights,
    rubric_version,
    trait_level_descriptor,
    trait_score_adjustments,
)
from app.domain.scoring_engine.trait_definitions import LEVEL_ORDER, TraitLevel

RUBRIC_VERSION = rubric_version()

TRAIT_LEVEL_HINTS: dict[str, dict[str, str]] = {
    tid: (load_trait_rubric_document().get("traits") or {}).get(tid, {}).get("levels") or {}
    for tid in [f"T{i}" for i in range(1, 9)]
}


def _condition_tokens(condition: str) -> list[str]:
    parts = re.split(r"[，、；。/]", condition)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _rubric_condition_met(condition: str, essay: str, bundle: TraitEvidenceBundle) -> bool:
    corpus = essay + " " + " ".join(bundle.positive) + " " + " ".join(bundle.negative)
    for tok in _condition_tokens(condition):
        if tok in corpus:
            return True
    return False


def trait_level_from_rubric(
    trait_id: str,
    *,
    heuristic_level: TraitLevel,
    bundle: TraitEvidenceBundle,
    essay: str = "",
) -> TraitLevel:
    """R-04：在启发式等级基础上，用 Rubric 加减分条件 + 证据 grounding 做确定性微调。"""
    adj = trait_score_adjustments(trait_id)
    plus_hits = sum(1 for c in adj["plus_conditions"] if _rubric_condition_met(c, essay, bundle))
    minus_hits = sum(1 for c in adj["minus_conditions"] if _rubric_condition_met(c, essay, bundle))
    idx = LEVEL_ORDER.index(heuristic_level)
    if minus_hits >= 1 and (bundle.grounding_rate < 0.7 or len(bundle.negative) >= 1):
        idx = max(0, idx - 1)
    elif minus_hits >= 2:
        idx = max(0, idx - 1)
    elif plus_hits >= 2 and bundle.grounding_rate >= 0.8 and len(bundle.positive) >= 1:
        idx = min(len(LEVEL_ORDER) - 1, idx + 1)
    return LEVEL_ORDER[idx]


__all__ = [
    "RUBRIC_VERSION",
    "TRAIT_LEVEL_HINTS",
    "assert_rubric_complete",
    "merged_scorable_weights",
    "trait_level_descriptor",
    "trait_level_from_rubric",
]
