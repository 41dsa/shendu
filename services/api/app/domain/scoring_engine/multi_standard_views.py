"""PRD §6.5：严格 / 宽松 / 标准依赖型多视图（区间与 C 档诊断）。"""

from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.multi_standard_view_copy import format_c_trait_dispute, score_view_labels
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard
from app.domain.scoring_engine.trait_definitions import TraitDiagnostic
from app.domain.scoring_engine.trait_interval import TraitIntervalEstimate, estimate_score_interval


def _interval_payload(est: TraitIntervalEstimate) -> dict[str, Any]:
    return {
        "ability_level": est.ability_level,
        "score_min": est.score_min,
        "score_max": est.score_max,
        "system_center": est.system_center,
        "uncalibrated": est.uncalibrated,
        "primary_loss_traits": list(est.primary_loss_traits),
    }


def build_multi_standard_views(
    diagnostics: list[TraitDiagnostic],
    *,
    max_score: float,
    severe_off_topic: bool,
    standard: QuestionStandardCard | None,
    baseline: TraitIntervalEstimate | None = None,
) -> dict[str, Any]:
    base = baseline or estimate_score_interval(
        diagnostics,
        max_score=max_score,
        severe_off_topic=severe_off_topic,
        standard=standard,
        aggregate="weighted",
    )
    strict = estimate_score_interval(
        diagnostics,
        max_score=max_score,
        severe_off_topic=severe_off_topic,
        standard=standard,
        aggregate="min",
    )
    loose = estimate_score_interval(
        diagnostics,
        max_score=max_score,
        severe_off_topic=severe_off_topic,
        standard=standard,
        aggregate="max",
    )
    labels = score_view_labels()
    dependency_traits = [
        {
            "trait_id": d.trait_id,
            "name": d.name,
            "level": d.level,
            "dispute_hint": d.dispute_hint
            or format_c_trait_dispute(trait_id=d.trait_id, trait_name=d.name, level=d.level or "L2"),
            "conclusion": d.conclusion,
        }
        for d in diagnostics
        if d.standard_tier == "C"
    ]
    return {
        "labels": labels,
        "baseline": _interval_payload(base),
        "strict": _interval_payload(strict),
        "loose": _interval_payload(loose),
        "dependency": {
            "label": labels.get("dependency") or "标准依赖型维度（不参与得分合成）",
            "traits": dependency_traits,
            "dispute_notes": [d.dispute_hint for d in diagnostics if d.dispute_hint],
        },
    }
