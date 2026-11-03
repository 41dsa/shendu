"""V1 评分引擎：题目标准 → 硬规则 → 证据 → Trait → 边界 → 区间 → 置信度。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.scoring_engine.essay_signals import EssaySignals, analyze_essay_signals
from app.domain.scoring_engine.boundary_policy import apply_boundary_policy
from app.domain.scoring_engine.hard_rules import HardRuleReport, run_hard_rules
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard
from app.domain.scoring_engine.trait_confidence import compute_trait_engine_confidence
from app.domain.scoring_engine.trait_definitions import TraitDiagnostic
from app.domain.scoring_engine.evidence_engine import EvidenceEngineResult, extract_evidence
from app.domain.scoring_engine.trait_evaluator import evaluate_traits_with_evidence
from app.domain.scoring_engine.trait_interval import TraitIntervalEstimate, estimate_score_interval
from app.domain.scoring_engine.types import EngineLayerTrace


@dataclass
class TraitEngineResult:
    standard: QuestionStandardCard
    signals: EssaySignals
    hard_rules: HardRuleReport
    evidence: EvidenceEngineResult
    diagnostics: list[TraitDiagnostic]
    interval: TraitIntervalEstimate
    confidence: float
    suppress_absolute_score: bool
    dispute_notes: list[str] = field(default_factory=list)
    traces: list[EngineLayerTrace] = field(default_factory=list)


def _boundary_check(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> list[str]:
    notes: list[str] = []
    if hard.severe_off_topic and interval.system_center > max_score * 0.4:
        notes.append("严重跑题信号与区间估计冲突，已下调中心值。")
    if hard.flags.get("mechanical_copy"):
        notes.append("机械摘抄材料信号明显，材料转化维度应重点失分。")
    return notes


def run_trait_pipeline(
    essay: str,
    standard: QuestionStandardCard,
    *,
    word_min: int,
    word_max: int,
    reference_material: str,
    max_score: float,
    word_ratio: float,
    force_diagnostic_only: bool = False,
    model_vote_spread: float = 0.0,
    llm_evidence_by_trait: dict[str, dict] | None = None,
) -> TraitEngineResult:
    signals = analyze_essay_signals(essay, standard)
    must_avoid = list(standard.off_topic_hints or []) + list(standard.severe_off_topic_hints or [])
    must_address = list(standard.core_theses or []) + list(standard.keywords or [])[:6]
    hard = run_hard_rules(
        essay,
        word_min=word_min,
        word_max=word_max,
        reference_material=reference_material,
        main_point_hit=signals.main_thesis_signal,
        proposition_task=f"{standard.task} {standard.theme}".strip(),
        must_avoid=must_avoid,
        must_address=must_address,
    )
    evidence_result = extract_evidence(
        essay,
        signals,
        hard,
        standard,
        llm_by_trait=llm_evidence_by_trait,
    )
    diagnostics = evaluate_traits_with_evidence(signals, hard, evidence_result, essay=essay)
    from app.services.scoring_engine.v3_model_router import maybe_apply_v3_trait_model

    diagnostics, v3_traces = maybe_apply_v3_trait_model(diagnostics)
    interval = estimate_score_interval(
        diagnostics,
        max_score=max_score,
        severe_off_topic=hard.severe_off_topic or signals.off_topic_signal,
        standard=standard,
    )
    interval, policy_notes = apply_boundary_policy(hard, interval, max_score=max_score)
    boundary_notes = _boundary_check(hard, interval, max_score) + policy_notes

    conf, suppress = compute_trait_engine_confidence(
        diagnostics,
        standard_match_confidence=standard.match_confidence,
        word_ratio=word_ratio,
        model_vote_spread=model_vote_spread,
        evidence_grounding_rate=evidence_result.overall_grounding_rate,
    )
    if force_diagnostic_only:
        suppress = True

    disputes = [d.dispute_hint for d in diagnostics if d.dispute_hint]
    traces = [
        EngineLayerTrace(
            layer="question_standard",
            detail="matched",
            data={
                "version": standard.version,
                "review_status": standard.review_status,
                "reviewed": standard.reviewed,
                "match_confidence": standard.match_confidence,
            },
        ),
        EngineLayerTrace(
            layer="rule_detection",
            detail="hard_rules",
            data={"flags": hard.flags, "format_issues": hard.format_issues},
        ),
        EngineLayerTrace(
            layer="boundary_policy",
            detail="applied",
            data={"notes": boundary_notes},
        ),
        EngineLayerTrace(
            layer="evidence_engine",
            detail="rule_extract",
            data={
                "grounding_rate": evidence_result.overall_grounding_rate,
                "rejected_count": len(evidence_result.rejected_quotes),
            },
        ),
        EngineLayerTrace(
            layer="evidence",
            detail="essay_signals",
            data={
                "keyword_coverage": signals.keyword_coverage,
                "paragraphs": len(signals.paragraphs),
                "argument_markers": signals.argument_markers,
            },
        ),
        EngineLayerTrace(
            layer="trait_scoring",
            detail="levels",
            data={d.trait_id: d.level for d in diagnostics},
        ),
        EngineLayerTrace(
            layer="interval_estimate",
            detail="range",
            data={
                "ability": interval.ability_level,
                "range": [interval.score_min, interval.score_max],
                "center": interval.system_center,
            },
        ),
        *v3_traces,
    ]
    return TraitEngineResult(
        standard=standard,
        signals=signals,
        hard_rules=hard,
        evidence=evidence_result,
        diagnostics=diagnostics,
        interval=interval,
        confidence=conf,
        suppress_absolute_score=suppress,
        dispute_notes=disputes + boundary_notes,
        traces=traces,
    )


def trait_diagnostics_to_payload(
    diagnostics: list[TraitDiagnostic],
    *,
    evidence_meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_trait = (evidence_meta or {}).get("by_trait") or {}
    for d in diagnostics:
        meta = by_trait.get(d.trait_id) or {}
        rows.append(
            {
                "trait_id": d.trait_id,
                "name": d.name,
                "standard_tier": d.standard_tier,
                "level": d.level,
                "participates_in_score": d.participates_in_score,
                "confidence": d.confidence,
                "evidence_positive": list(d.evidence.positive),
                "evidence_negative": list(d.evidence.negative),
                "evidence_missing": list(d.evidence.missing),
                "evidence_grounding_rate": meta.get("grounding_rate"),
                "evidence_spans": list(meta.get("evidence_spans") or []),
                "conclusion": d.conclusion,
                "dispute_hint": d.dispute_hint,
            }
        )
    return rows


def evidence_meta_from_result(evidence_result) -> dict[str, Any]:
    def _spans(bundle) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for sp in bundle.spans or []:
            out.append(
                {
                    "quote": sp.quote,
                    "para": sp.para,
                    "start": sp.start,
                    "end": sp.end,
                    "grounded": sp.grounded,
                }
            )
        return out

    return {
        "overall_grounding_rate": evidence_result.overall_grounding_rate,
        "by_trait": {
            tid: {
                "grounding_rate": b.grounding_rate,
                "evidence_spans": _spans(b),
            }
            for tid, b in evidence_result.by_trait.items()
        },
    }
