"""PRD ⑦ Trait 分项等级判定：Evidence → Rubric 定级（B 档）/ 诊断（C 档）。"""

from __future__ import annotations

from app.domain.scoring_engine.evidence_engine import EvidenceEngineResult, bundle_to_trait_evidence
from app.domain.scoring_engine.essay_signals import EssaySignals
from app.domain.scoring_engine.hard_rules import HardRuleReport
from app.domain.scoring_engine.rubric_engine import trait_level_descriptor
from app.domain.scoring_engine.multi_standard_view_copy import format_c_trait_dispute
from app.domain.scoring_engine.rubric_trait_level import B_TRAITS, level_for_b_trait, level_for_c_trait
from app.domain.scoring_engine.trait_definitions import TRAIT_SPECS, TraitDiagnostic, TraitLevel


def _trait_confidence(
    level: TraitLevel | None,
    bundle_grounding: float,
    hard_penalty: bool,
    *,
    has_positive: bool,
) -> float:
    base = 0.82
    if not has_positive:
        base -= 0.1
    if bundle_grounding < 0.85:
        base -= 0.08
    if hard_penalty:
        base -= 0.05
    if level in ("L0", "L1"):
        base += 0.03
    return round(max(0.48, min(0.93, base)), 2)


def evaluate_traits_with_evidence(
    signals: EssaySignals,
    hard: HardRuleReport,
    evidence: EvidenceEngineResult,
    *,
    essay: str = "",
) -> list[TraitDiagnostic]:
    out: list[TraitDiagnostic] = []
    for tid, spec in TRAIT_SPECS.items():
        bundle = evidence.by_trait[tid]
        ev = bundle_to_trait_evidence(bundle)

        if spec.standard_tier == "B" and tid in B_TRAITS:
            level = level_for_b_trait(tid, signals, hard, bundle, essay=essay)
        else:
            level = level_for_c_trait(tid, signals, bundle, essay=essay)

        conf = _trait_confidence(
            level,
            bundle.grounding_rate,
            bool(hard.format_issues),
            has_positive=bool(ev.positive),
        )
        hint = trait_level_descriptor(tid, level or "L2")
        dispute = ""
        conclusion = f"{spec.name}：{level}。{hint}".strip()
        if spec.standard_tier == "C":
            dispute = format_c_trait_dispute(trait_id=tid, trait_name=spec.name, level=level or "L2")
            conclusion = f"诊断 {level}（不参与得分合成）。{hint}"

        out.append(
            TraitDiagnostic(
                trait_id=tid,
                name=spec.name,
                standard_tier=spec.standard_tier,
                level=level,
                participates_in_score=spec.participates_in_score,
                confidence=conf,
                evidence=ev,
                conclusion=conclusion,
                dispute_hint=dispute,
            )
        )
    return out


def evaluate_traits_from_signals(
    signals: EssaySignals,
    hard: HardRuleReport,
    evidence: EvidenceEngineResult | None = None,
) -> list[TraitDiagnostic]:
    """兼容旧调用：无 evidence 时由 pipeline 保证传入。"""
    if evidence is None:
        raise ValueError("evidence required; use trait_pipeline.run_trait_pipeline")
    return evaluate_traits_with_evidence(signals, hard, evidence)
