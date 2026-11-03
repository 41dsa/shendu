"""PRD §6.2 / AN-04：锚作文相对尺度（最近邻 + Trait 对比）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.trait_definitions import level_to_numeric
from app.models.entities import AnchorEssay


def count_published_anchors(db: Session, question_id: str) -> int:
    if not question_id:
        return int(settings.trait_anchor_count)
    return (
        db.query(AnchorEssay)
        .filter(AnchorEssay.question_id == question_id, AnchorEssay.is_published.is_(True))
        .count()
    )


def _trait_vector(levels: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for tid in (f"T{i}" for i in range(1, 9)):
        lv = levels.get(tid)
        if lv:
            out[tid] = level_to_numeric(str(lv))
    return out


def _distance(a: dict[str, int], b: dict[str, int]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 999.0
    return sum(abs(a.get(k, 2) - b.get(k, 2)) for k in keys) / len(keys)


def nearest_anchor_match(
    db: Session,
    *,
    question_id: str,
    essay_trait_levels: dict[str, str],
) -> dict[str, Any] | None:
    rows = (
        db.query(AnchorEssay)
        .filter(AnchorEssay.question_id == question_id, AnchorEssay.is_published.is_(True))
        .all()
    )
    if len(rows) < settings.anchor_min_for_relative_scale:
        return None
    essay_vec = _trait_vector(essay_trait_levels)
    best: AnchorEssay | None = None
    best_dist = 999.0
    for row in rows:
        dist = _distance(essay_vec, _trait_vector(row.trait_levels or {}))
        if dist < best_dist:
            best_dist = dist
            best = row
    if not best:
        return None
    gaps = []
    anchor_levels = best.trait_levels or {}
    for tid, n in essay_vec.items():
        anchor_lv = str(anchor_levels.get(tid) or "L2")
        gaps.append(
            {
                "trait_id": tid,
                "essay_level": f"L{n}",
                "anchor_level": anchor_lv,
                "delta": n - level_to_numeric(anchor_lv),
            }
        )
    return {
        "anchor_count": len(rows),
        "nearest_anchor_id": best.id,
        "nearest_anchor_title": best.title,
        "distance": round(best_dist, 3),
        "trait_gaps": gaps,
    }


def resolve_anchor_count(db: Session | None, ctx) -> int:
    if getattr(ctx, "anchor_count", None) is not None:
        return int(ctx.anchor_count)
    qid = getattr(ctx, "question_id", "") or ""
    if db and qid:
        return count_published_anchors(db, qid)
    return int(settings.trait_anchor_count)


def essay_trait_levels_from_diagnostics(trait_rows: list[dict[str, Any]]) -> dict[str, str]:
    return {str(r.get("trait_id")): str(r.get("level") or "") for r in trait_rows if r.get("trait_id")}
