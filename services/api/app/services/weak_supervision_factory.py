"""PRD §7.4 弱监督数据工厂（V1 最小集）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.scoring_engine.trait_definitions import level_to_numeric
from app.domain.scoring_engine.types import ScoringEngineResult
from app.models.entities import WeakLabel, WeakLabelType

COUNTEREXAMPLE_TEMPLATES: list[dict[str, Any]] = [
    {
        "trait_id": "T1",
        "label_value": "off_topic_pattern",
        "payload": {"pattern": "严重跑题", "hint": "全文未回应题干关键词"},
    },
    {
        "trait_id": "T4",
        "label_value": "mechanical_copy_pattern",
        "payload": {"pattern": "机械摘抄", "hint": "大段照搬材料未转化"},
    },
    {
        "trait_id": "T3",
        "label_value": "structure_stack_pattern",
        "payload": {"pattern": "堆砌", "hint": "段落过多但缺少论证推进"},
    },
]


def weak_label_export_row(row: WeakLabel) -> dict[str, Any]:
    return {
        "id": row.id,
        "is_weak_label": True,
        "label_type": row.label_type.value,
        "trait_id": row.trait_id,
        "label_value": row.label_value,
        "submission_id": row.submission_id,
        "grading_job_id": row.grading_job_id,
        "question_id": row.question_id,
        "rubric_version": row.rubric_version,
        "standard_version": row.standard_version,
        "payload": row.payload,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def export_weak_labels(db: Session, *, limit: int = 5000) -> list[dict[str, Any]]:
    rows = db.query(WeakLabel).order_by(WeakLabel.created_at.desc()).limit(limit).all()
    out = [weak_label_export_row(r) for r in rows]
    for item in out:
        assert item["is_weak_label"] is True
    return out


def _add_label(
    db: Session,
    *,
    label_type: WeakLabelType,
    label_value: str,
    trait_id: str | None,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    rubric_version: str,
    standard_version: int | None,
    payload: dict[str, Any],
) -> None:
    db.add(
        WeakLabel(
            grading_job_id=grading_job_id,
            submission_id=submission_id,
            question_id=question_id,
            label_type=label_type,
            trait_id=trait_id,
            label_value=label_value,
            is_weak_label=True,
            rubric_version=rubric_version,
            standard_version=standard_version,
            payload=payload,
        )
    )


def labels_from_engine_result(result: ScoringEngineResult) -> list[dict[str, Any]]:
    """纯函数：由引擎结果推导应写入的弱标签描述（供单测）。"""
    labels: list[dict[str, Any]] = []
    for flag, val in (result.hard_rule_flags or {}).items():
        if val:
            labels.append(
                {
                    "label_type": WeakLabelType.rule.value,
                    "trait_id": None,
                    "label_value": str(flag),
                    "payload": {"hard_rule": flag},
                }
            )
    for row in result.trait_diagnostics or []:
        tid = str(row.get("trait_id") or "")
        level = str(row.get("level") or "")
        labels.append(
            {
                "label_type": WeakLabelType.rubric.value,
                "trait_id": tid,
                "label_value": level,
                "payload": {
                    "source": "trait_rubric_engine",
                    "confidence": row.get("confidence"),
                    "evidence_insufficient": row.get("evidence_insufficient"),
                    "evidence_positive_count": len(row.get("evidence_positive") or []),
                    "evidence_grounding_rate": row.get("evidence_grounding_rate"),
                    "participates_in_score": row.get("participates_in_score"),
                },
            }
        )
        votes = row.get("model_votes") or []
        if len(votes) >= 2:
            levels = [str(v.get("level") or "") for v in votes if v.get("level")]
            spread = row.get("vote_spread")
            if spread is not None and float(spread) <= 0.25 and len(set(levels)) == 1:
                labels.append(
                    {
                        "label_type": WeakLabelType.model_consensus.value,
                        "trait_id": tid,
                        "label_value": levels[0],
                        "payload": {"model_votes": votes, "vote_spread": spread},
                    }
                )
            elif spread is not None and float(spread) >= 0.5:
                labels.append(
                    {
                        "label_type": WeakLabelType.self_consistency.value,
                        "trait_id": tid,
                        "label_value": "high_spread",
                        "payload": {"model_votes": votes, "vote_spread": spread},
                    }
                )
    max_spread = float(result.trait_vote_max_spread or 0)
    voted_rows = [r for r in (result.trait_diagnostics or []) if len(r.get("model_votes") or []) >= 2]
    if max_spread <= 0.25 and len(voted_rows) >= 2:
        labels.append(
            {
                "label_type": WeakLabelType.model_consensus.value,
                "trait_id": None,
                "label_value": "engine_high_consensus",
                "payload": {
                    "trait_vote_max_spread": max_spread,
                    "voted_trait_count": len(voted_rows),
                    "is_weak_label": True,
                },
            }
        )
    return labels


def persist_weak_labels_from_engine(
    db: Session,
    *,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    result: ScoringEngineResult,
    standard_version: int | None = None,
) -> int:
    rubric_version = result.rubric_version or result.point_pool_version or ""
    count = 0
    for spec in labels_from_engine_result(result):
        _add_label(
            db,
            label_type=WeakLabelType(spec["label_type"]),
            label_value=str(spec["label_value"]),
            trait_id=spec.get("trait_id"),
            grading_job_id=grading_job_id,
            submission_id=submission_id,
            question_id=question_id,
            rubric_version=rubric_version,
            standard_version=standard_version,
            payload=dict(spec.get("payload") or {}),
        )
        count += 1
    return count


def persist_retry_trait_delta(
    db: Session,
    *,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    prior_traits: list[dict[str, Any]],
    current_traits: list[dict[str, Any]],
    rubric_version: str,
) -> int:
    prior = {str(r.get("trait_id")): r for r in prior_traits}
    count = 0
    for cur in current_traits:
        tid = str(cur.get("trait_id") or "")
        if not tid or tid not in prior:
            continue
        p_lv = prior[tid].get("level")
        c_lv = cur.get("level")
        if p_lv == c_lv:
            continue
        delta = level_to_numeric(c_lv) - level_to_numeric(p_lv) if c_lv and p_lv else 0
        _add_label(
            db,
            label_type=WeakLabelType.retry_delta,
            label_value=f"{p_lv}->{c_lv}",
            trait_id=tid,
            grading_job_id=grading_job_id,
            submission_id=submission_id,
            question_id=question_id,
            rubric_version=rubric_version,
            standard_version=None,
            payload={"prior_level": p_lv, "current_level": c_lv, "delta_numeric": delta},
        )
        count += 1
    return count


def ensure_counterexample_templates(db: Session, *, question_id: str | None = None) -> int:
    """W-06：全局反例模板（每题可复用，question_id 可为空表示模板库）。"""
    existing = (
        db.query(WeakLabel)
        .filter(
            WeakLabel.label_type == WeakLabelType.counterexample,
            WeakLabel.question_id == question_id,
        )
        .count()
    )
    if existing >= len(COUNTEREXAMPLE_TEMPLATES):
        return 0
    added = 0
    for tpl in COUNTEREXAMPLE_TEMPLATES:
        dup = (
            db.query(WeakLabel)
            .filter(
                WeakLabel.label_type == WeakLabelType.counterexample,
                WeakLabel.label_value == tpl["label_value"],
                WeakLabel.question_id == question_id,
            )
            .first()
        )
        if dup:
            continue
        db.add(
            WeakLabel(
                question_id=question_id,
                label_type=WeakLabelType.counterexample,
                trait_id=tpl.get("trait_id"),
                label_value=str(tpl["label_value"]),
                is_weak_label=True,
                payload=dict(tpl.get("payload") or {}),
            )
        )
        added += 1
    return added
