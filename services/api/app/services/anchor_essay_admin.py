"""锚作文运营：按题统计、演示种子数据。"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import AnchorEssay, Question

DEMO_LEVELS = ("L0", "L1", "L2", "L3", "L4")


def seed_demo_anchors_for_question(db: Session, question_id: str) -> dict:
    question = db.get(Question, question_id)
    if not question:
        raise ValueError("题目不存在")
    added = 0
    for i, lv in enumerate(DEMO_LEVELS):
        title = f"演示锚作文-{lv}"
        exists = (
            db.query(AnchorEssay)
            .filter(AnchorEssay.question_id == question_id, AnchorEssay.title == title)
            .first()
        )
        if exists:
            continue
        traits = {f"T{t}": lv if t <= 5 else "L2" for t in range(1, 9)}
        db.add(
            AnchorEssay(
                question_id=question_id,
                title=title,
                content=f"【{lv} 档演示锚】推进基层治理现代化。\n\n" + "论证段落。\n\n" * (3 + i),
                aggregate_level=lv,
                trait_levels=traits,
                is_published=True,
            )
        )
        added += 1
    db.commit()
    return {"question_id": question_id, "added": added, "levels": list(DEMO_LEVELS)}


def anchor_essays_summary_by_question(db: Session) -> list[dict]:
    min_rel = int(settings.anchor_min_for_relative_scale)
    min_center = int(settings.anchor_min_for_center_score)
    from sqlalchemy import case

    published_count = func.sum(case((AnchorEssay.is_published.is_(True), 1), else_=0)).label("published")
    total_count = func.count(AnchorEssay.id).label("total")
    rows = (
        db.query(
            AnchorEssay.question_id,
            total_count,
            published_count,
        )
        .group_by(AnchorEssay.question_id)
        .all()
    )
    qids = [r.question_id for r in rows]
    titles: dict[str, str] = {}
    if qids:
        for q in db.query(Question.id, Question.title).filter(Question.id.in_(qids)).all():
            titles[q.id] = q.title or q.id

    out: list[dict] = []
    for r in rows:
        pub = int(r.published or 0)
        tot = int(r.total or 0)
        out.append(
            {
                "question_id": r.question_id,
                "question_title": titles.get(r.question_id, r.question_id),
                "published_count": pub,
                "total_count": tot,
                "relative_scale_ready": pub >= min_rel,
                "center_score_ready": pub >= min_center,
                "target_band_min": 10,
                "target_band_max": 20,
                "in_target_band": 10 <= pub <= 20,
            }
        )
    out.sort(key=lambda x: x["published_count"])
    return out
