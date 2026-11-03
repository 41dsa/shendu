"""B 档 Trait：由 Rubric + 已 grounding 证据 + 信号确定性定级。"""

from __future__ import annotations

from app.domain.scoring_engine.evidence_engine import TraitEvidenceBundle
from app.domain.scoring_engine.essay_signals import EssaySignals
from app.domain.scoring_engine.hard_rules import HardRuleReport
from app.domain.scoring_engine.rubric_engine import trait_level_from_rubric
from app.domain.scoring_engine.trait_definitions import TraitId, TraitLevel, level_from_ratio

B_TRAITS: tuple[TraitId, ...] = ("T1", "T3", "T4", "T5", "T8")


def _evidence_score(bundle: TraitEvidenceBundle) -> float:
    score = 0.35
    score += min(0.35, len(bundle.positive) * 0.1)
    score -= min(0.2, len(bundle.negative) * 0.08)
    score -= min(0.15, len(bundle.missing) * 0.05)
    score *= bundle.grounding_rate
    return max(0.0, min(1.0, score))


def level_for_b_trait(
    tid: TraitId,
    signals: EssaySignals,
    hard: HardRuleReport,
    bundle: TraitEvidenceBundle,
    *,
    essay: str = "",
) -> TraitLevel:
    ev_ratio = _evidence_score(bundle)

    heuristic: TraitLevel
    if tid == "T1":
        if hard.severe_off_topic or signals.off_topic_signal:
            heuristic = "L0"
        else:
            base = signals.keyword_coverage * 0.55 + (0.25 if signals.main_thesis_signal else 0) + ev_ratio * 0.2
            heuristic = level_from_ratio(base)
    elif tid == "T3":
        base = signals.structure_score * 0.7 + ev_ratio * 0.3
        if hard.flags.get("structure_incomplete"):
            heuristic = "L0" if base < 0.4 else "L1"
        else:
            heuristic = level_from_ratio(base)
    elif tid == "T4":
        mat = min(1.0, len(signals.material_use_hits) / 3.0) * 0.5 + ev_ratio * 0.5
        if hard.flags.get("mechanical_copy"):
            heuristic = "L0" if mat < 0.5 else "L1"
        else:
            heuristic = level_from_ratio(mat)
    elif tid == "T5":
        arg = min(1.0, signals.argument_markers / 8.0) * 0.55 + ev_ratio * 0.45
        heuristic = level_from_ratio(arg)
    elif tid == "T8":
        lang = (0.65 if not hard.format_issues else 0.4) * 0.6 + ev_ratio * 0.4
        if hard.flags.get("word_short"):
            lang -= 0.12
        heuristic = level_from_ratio(max(0.0, lang))
    else:
        heuristic = "L2"
    return trait_level_from_rubric(tid, heuristic_level=heuristic, bundle=bundle, essay=essay)


def level_for_c_trait(
    tid: TraitId,
    signals: EssaySignals,
    bundle: TraitEvidenceBundle,
    *,
    essay: str = "",
) -> TraitLevel:
    base = signals.keyword_coverage * 0.4 + _evidence_score(bundle) * 0.6
    if tid == "T6":
        base = min(1.0, signals.argument_markers / 8.0) * 0.5 + _evidence_score(bundle) * 0.5
    if tid == "T7":
        base = 0.45 + _evidence_score(bundle) * 0.3
    heuristic = level_from_ratio(base)
    return trait_level_from_rubric(tid, heuristic_level=heuristic, bundle=bundle, essay=essay)
