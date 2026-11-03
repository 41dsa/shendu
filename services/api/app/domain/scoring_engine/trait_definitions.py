"""PRD V1：八大 Trait 定义、L0–L4 等级与 A/B/C 档策略。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.domain.scoring_engine.rubric_loader import ability_by_level, default_scorable_weights, load_trait_rubric_document

TraitId = Literal["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8"]
TraitLevel = Literal["L0", "L1", "L2", "L3", "L4"]
TraitStandardTier = Literal["A", "B", "C"]

LEVEL_ORDER: tuple[TraitLevel, ...] = ("L0", "L1", "L2", "L3", "L4")

ABILITY_BY_LEVEL: dict[TraitLevel, str] = {
    k: v for k, v in ability_by_level().items() if k in LEVEL_ORDER  # type: ignore[misc]
}

# B 档参与区间合成；C 档仅诊断
SCORABLE_TRAIT_WEIGHTS: dict[str, float] = default_scorable_weights()


@dataclass(frozen=True)
class TraitSpec:
    trait_id: TraitId
    name: str
    standard_tier: TraitStandardTier
    participates_in_score: bool
    dimension_ids: tuple[str, ...] = ()


def _build_trait_specs() -> dict[TraitId, TraitSpec]:
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    specs: dict[TraitId, TraitSpec] = {}
    for i in range(1, 9):
        tid = f"T{i}"  # type: ignore[assignment]
        row = traits.get(tid) or {}
        dims = row.get("dimension_ids") or []
        specs[tid] = TraitSpec(
            trait_id=tid,
            name=str(row.get("name") or tid),
            standard_tier=str(row.get("standard_tier") or "B"),  # type: ignore[arg-type]
            participates_in_score=bool(row.get("participates_in_score", True)),
            dimension_ids=tuple(str(d) for d in dims),
        )
    return specs


TRAIT_SPECS: dict[TraitId, TraitSpec] = _build_trait_specs()


@dataclass
class TraitEvidence:
    positive: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class TraitDiagnostic:
    trait_id: TraitId
    name: str
    standard_tier: TraitStandardTier
    level: TraitLevel | None
    participates_in_score: bool
    confidence: float
    evidence: TraitEvidence
    conclusion: str = ""
    dispute_hint: str = ""


def level_from_ratio(ratio: float) -> TraitLevel:
    if ratio >= 0.88:
        return "L4"
    if ratio >= 0.72:
        return "L3"
    if ratio >= 0.55:
        return "L2"
    if ratio >= 0.35:
        return "L1"
    return "L0"


def level_to_numeric(level: TraitLevel) -> int:
    return LEVEL_ORDER.index(level)
