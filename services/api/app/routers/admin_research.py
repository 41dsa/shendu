import csv
import io
import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models.entities import (
    AnalyticsEvent,
    DisputeStatus,
    GoldSample,
    GoldRun,
    GradingJob,
    PromptPurpose,
    PromptVersion,
    Question,
    QuestionType,
    ScoreDispute,
    User,
)
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.schemas.admin_research import (
    AdminQuestionUpsert,
    GoldSampleCreate,
    AnchorEssayPatch,
    AnchorEssayUpsert,
    AnchorTraitReviewBatchCreate,
    AnchorTraitReviewCreate,
    PairCompareComplete,
    PairCompareCreate,
    PromptVersionCreate,
    PromptVersionUpdate,
)
from app.services.gold_ai_service import seed_ai_gold_for_question_sync
from app.services.gold_service import regression_summary, run_gold_sample_sync
from app.services.mstd_e_ai_eval import evaluate_mstd_e_ai_milestone
from app.services.events_service import track_event

router = APIRouter(prefix="/admin", tags=["admin-research"])


# --- 大作文题库 CRUD（BE-602） ---


@router.get("/questions")
def admin_list_questions(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    from app.services.standard_engine.question_standard_link import bulk_standard_links

    rows = (
        db.query(Question)
        .filter(Question.id != USER_ESSAY_QUESTION_ID)
        .order_by(Question.title)
        .all()
    )
    links = bulk_standard_links(db, [r.id for r in rows])
    return [
        {
            "id": r.id,
            "title": r.title,
            "prompt": r.prompt,
            "material": r.material,
            "score": r.score,
            "word_limit": r.word_limit,
            "material_structured": r.material_structured,
            "scoring_points": r.scoring_points,
            "published": r.published,
            "standard_link": links.get(r.id),
            "essay_item_locked": bool((r.material_structured or {}).get("essay_item_v1_locked")),
        }
        for r in rows
    ]


@router.get("/questions/{question_id}/standard-link")
def get_question_standard_link(
    question_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.standard_engine.question_standard_link import standard_link_for_question

    if not db.get(Question, question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    return standard_link_for_question(db, question_id)


@router.post("/questions")
def admin_create_question(
    body: AdminQuestionUpsert,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = Question(
        title=body.title,
        question_type=QuestionType.essay,
        prompt=body.prompt,
        material=body.material,
        score=body.score,
        word_limit=body.word_limit,
        material_structured={"genre": "essay", "word_min": body.word_min, "word_max": body.word_max},
        scoring_points=body.scoring_points,
        published=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    track_event(db, "admin_question_create", admin.id, question_id=row.id)
    return {"id": row.id}


@router.put("/questions/{question_id}")
def admin_update_question(
    question_id: str,
    body: AdminQuestionUpsert,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Question, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="题目不存在")
    if question_id == USER_ESSAY_QUESTION_ID:
        raise HTTPException(status_code=403, detail="系统占位题不可编辑")
    from app.services.standard_engine.essay_item_import_service import is_essay_item_locked, locked_field_violations

    patch = {
        "title": body.title,
        "prompt": body.prompt,
        "material": body.material,
        "score": body.score,
        "material_structured": {"word_min": body.word_min, "word_max": body.word_max},
    }
    violations = locked_field_violations(row, patch)
    if violations:
        raise HTTPException(
            status_code=400,
            detail="EssayItem A 类字段已锁定，不可修改: " + ", ".join(sorted(set(violations))),
        )
    if not is_essay_item_locked(row):
        row.title = body.title
        row.prompt = body.prompt
        row.material = body.material
        row.score = body.score
        row.word_limit = body.word_limit
        meta = dict(row.material_structured or {})
        meta.update({"genre": "essay", "word_min": body.word_min, "word_max": body.word_max})
        row.material_structured = meta
    row.scoring_points = body.scoring_points
    row.published = False
    db.commit()
    track_event(db, "admin_question_update", admin.id, question_id=row.id)
    return {"ok": True}


# --- Prompt 版本（BE-603） ---


@router.get("/prompt-versions")
def list_prompts(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(PromptVersion).order_by(PromptVersion.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "purpose": r.purpose.value,
            "is_active": r.is_active,
            "created_at": r.created_at.isoformat(),
            "content_preview": r.content[:120] + "…" if len(r.content) > 120 else r.content,
        }
        for r in rows
    ]


@router.post("/prompt-versions")
def create_prompt(
    body: PromptVersionCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    purpose = PromptPurpose(body.purpose)
    row = PromptVersion(name=body.name, purpose=purpose, content=body.content, is_active=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    track_event(db, "admin_prompt_create", admin.id, prompt_id=row.id)
    return {"id": row.id}


@router.post("/prompt-versions/{prompt_id}/activate")
def activate_prompt(
    prompt_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(PromptVersion, prompt_id)
    if not row:
        raise HTTPException(status_code=404, detail="版本不存在")
    for other in db.query(PromptVersion).filter(PromptVersion.purpose == row.purpose).all():
        other.is_active = False
    row.is_active = True
    db.commit()
    track_event(db, "admin_prompt_activate", admin.id, prompt_id=row.id)
    return {"ok": True}


@router.get("/prompt-versions/{prompt_id}")
def get_prompt_content(prompt_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    row = db.get(PromptVersion, prompt_id)
    if not row:
        raise HTTPException(status_code=404, detail="版本不存在")
    return {
        "id": row.id,
        "name": row.name,
        "purpose": row.purpose.value,
        "content": row.content,
        "is_active": row.is_active,
    }


@router.patch("/prompt-versions/{prompt_id}")
def update_prompt(
    prompt_id: str,
    body: PromptVersionUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(PromptVersion, prompt_id)
    if not row:
        raise HTTPException(status_code=404, detail="版本不存在")
    if body.name is not None:
        row.name = body.name.strip() or row.name
    if body.content is not None:
        row.content = body.content
    db.commit()
    track_event(db, "admin_prompt_update", admin.id, prompt_id=row.id)
    return {"ok": True, "id": row.id}


# --- 金标（BE-604/605） ---


@router.get("/gold-samples")
def list_gold(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(GoldSample).order_by(GoldSample.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "question_id": r.question_id,
            "title": r.title,
            "expected_score_min": r.expected_score_min,
            "expected_score_max": r.expected_score_max,
            "note": r.note,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/mstd-e-ai-milestone")
def mstd_e_ai_milestone(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    """纯 AI 验收里程碑（DEC-06～08）。"""
    return evaluate_mstd_e_ai_milestone(db)


@router.post("/gold-samples/seed-ai")
def seed_ai_gold(
    question_id: str = Query(...),
    mode: str = Query("auto", pattern="^(auto|stub|llm)$"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(Question, question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    try:
        rows = seed_ai_gold_for_question_sync(db, question_id, admin_user_id=admin.id, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"question_id": question_id, "count": len(rows), "ids": [r.id for r in rows]}


@router.post("/gold-samples")
def create_gold(
    body: GoldSampleCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(Question, body.question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    row = GoldSample(
        question_id=body.question_id,
        title=body.title,
        reference_answer=body.reference_answer,
        expected_score_min=body.expected_score_min,
        expected_score_max=body.expected_score_max,
        note=body.note,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    track_event(db, "admin_gold_create", admin.id, gold_sample_id=row.id)
    return {"id": row.id}


@router.post("/gold-samples/{sample_id}/run")
def run_gold(
    sample_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    sample = db.get(GoldSample, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="金标不存在")
    try:
        run = run_gold_sample_sync(db, sample, admin.id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"跑分失败: {exc}") from exc
    track_event(db, "admin_gold_run", admin.id, gold_sample_id=sample_id, run_id=run.id)
    return {
        "run_id": run.id,
        "ai_score": run.ai_score,
        "score_delta": run.score_delta,
        "standard_version": run.standard_version,
        "report_id": run.report_id,
    }


@router.get("/gold-regression")
def gold_regression(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    summary = regression_summary(db)
    recent = (
        db.query(GoldRun)
        .order_by(GoldRun.created_at.desc())
        .limit(20)
        .all()
    )
    summary["recent"] = [
        {
            "id": r.id,
            "gold_sample_id": r.gold_sample_id,
            "ai_score": r.ai_score,
            "score_delta": r.score_delta,
            "standard_version": r.standard_version,
            "created_at": r.created_at.isoformat(),
        }
        for r in recent
    ]
    return summary


# --- 批改任务查询（FE-605） ---


@router.get("/grading-jobs")
def admin_jobs(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(GradingJob).order_by(GradingJob.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "status": r.status.value,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


# --- 争议（BE-606/607） ---


@router.get("/disputes")
def list_disputes(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(ScoreDispute).order_by(ScoreDispute.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "report_id": r.report_id,
            "reason": r.reason,
            "status": r.status.value,
            "ai_review_note": r.ai_review_note,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.post("/disputes/{dispute_id}/ai-review")
def ai_review_dispute(
    dispute_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """
    AI 自动复核占位（BE-606）：V1 记录复核说明，完整二轮模型复核可接 P6+ job。
    """
    row = db.get(ScoreDispute, dispute_id)
    if not row:
        raise HTTPException(status_code=404, detail="争议不存在")
    row.status = DisputeStatus.ai_reviewed
    row.ai_review_note = "系统已登记争议，AI 深度复核队列待接入（当前维持原报告结论，请用户参考评分依据）。"
    row.resolved_at = datetime.now(UTC)
    db.commit()
    track_event(db, "admin_dispute_ai_review", admin.id, dispute_id=dispute_id)
    return {"ok": True}


@router.get("/disputes/export.csv")
def export_disputes(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = db.query(ScoreDispute).order_by(ScoreDispute.created_at.desc()).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "user_id", "report_id", "status", "reason", "created_at"])
    for r in rows:
        writer.writerow([r.id, r.user_id, r.report_id, r.status.value, r.reason, r.created_at.isoformat()])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=disputes.csv"},
    )


# --- PRD V1 锚作文（Phase 6） ---


@router.get("/anchor-essays/summary")
def anchor_essays_summary(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    from app.services.anchor_essay_admin import anchor_essays_summary_by_question

    return anchor_essays_summary_by_question(db)


@router.post("/anchor-essays/seed-demo")
def seed_demo_anchor_essays(
    question_id: str = Query(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.anchor_essay_admin import seed_demo_anchors_for_question

    try:
        return seed_demo_anchors_for_question(db, question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/anchor-essays")
def list_anchor_essays(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    question_id: str | None = None,
) -> list[dict]:
    from app.models.entities import AnchorEssay

    q = db.query(AnchorEssay).order_by(AnchorEssay.created_at.desc())
    if question_id:
        q = q.filter(AnchorEssay.question_id == question_id)
    rows = q.limit(200).all()
    return [
        {
            "id": r.id,
            "question_id": r.question_id,
            "title": r.title,
            "aggregate_level": r.aggregate_level,
            "trait_levels": r.trait_levels,
            "is_published": r.is_published,
            "content_preview": (r.content or "")[:120],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/anchor-essays")
def create_anchor_essay(
    body: AnchorEssayUpsert,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.entities import AnchorEssay

    row = AnchorEssay(
        question_id=body.question_id,
        title=body.title,
        content=body.content,
        aggregate_level=body.aggregate_level.upper()[:2] if body.aggregate_level else "L2",
        trait_levels=dict(body.trait_levels),
        is_published=body.is_published,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.get("/anchor-essays/{anchor_id}")
def get_anchor_essay(
    anchor_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.entities import AnchorEssay, AnchorTraitReview

    row = db.get(AnchorEssay, anchor_id)
    if not row:
        raise HTTPException(status_code=404, detail="锚作文不存在")
    reviews = (
        db.query(AnchorTraitReview)
        .filter(AnchorTraitReview.anchor_essay_id == anchor_id)
        .order_by(AnchorTraitReview.created_at.desc())
        .limit(500)
        .all()
    )
    return {
        "id": row.id,
        "question_id": row.question_id,
        "title": row.title,
        "content": row.content,
        "aggregate_level": row.aggregate_level,
        "trait_levels": row.trait_levels,
        "is_published": row.is_published,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reviews": [
            {
                "id": r.id,
                "reviewer_label": r.reviewer_label,
                "trait_id": r.trait_id,
                "level": r.level,
                "evidence_positive": list(r.evidence_positive or []),
                "reviewer_rationale": r.reviewer_rationale or "",
                "dispute_note": r.dispute_note,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
    }


@router.patch("/anchor-essays/{anchor_id}")
def patch_anchor_essay(
    anchor_id: str,
    body: AnchorEssayPatch,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.entities import AnchorEssay

    row = db.get(AnchorEssay, anchor_id)
    if not row:
        raise HTTPException(status_code=404, detail="锚作文不存在")
    patch = body.model_dump(exclude_none=True)
    if "aggregate_level" in patch and patch["aggregate_level"]:
        patch["aggregate_level"] = str(patch["aggregate_level"]).upper()[:2]
    if "trait_levels" in patch and patch["trait_levels"]:
        patch["trait_levels"] = {k.upper(): str(v).upper() for k, v in patch["trait_levels"].items()}
    for key, val in patch.items():
        setattr(row, key, val)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "is_published": row.is_published,
        "aggregate_level": row.aggregate_level,
    }


@router.post("/anchor-essays/{anchor_id}/reviews")
def add_anchor_trait_review(
    anchor_id: str,
    body: AnchorTraitReviewCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.entities import AnchorEssay, AnchorTraitReview

    anchor = db.get(AnchorEssay, anchor_id)
    if not anchor:
        raise HTTPException(status_code=404, detail="锚作文不存在")
    row = AnchorTraitReview(
        anchor_essay_id=anchor_id,
        reviewer_label=body.reviewer_label,
        trait_id=body.trait_id.upper(),
        level=body.level.upper(),
        evidence_positive=list(body.evidence_positive),
        reviewer_rationale=(body.reviewer_rationale or "")[:1024],
        dispute_note=body.dispute_note[:500],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.post("/anchor-essays/{anchor_id}/reviews/batch")
def add_anchor_trait_reviews_batch(
    anchor_id: str,
    body: AnchorTraitReviewBatchCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.entities import AnchorEssay, AnchorTraitReview

    anchor = db.get(AnchorEssay, anchor_id)
    if not anchor:
        raise HTTPException(status_code=404, detail="锚作文不存在")
    label = body.reviewer_label.strip()
    if not label:
        raise HTTPException(status_code=400, detail="请填写评者姓名")
    level = body.level.upper()
    if level not in ("L0", "L1", "L2", "L3", "L4"):
        raise HTTPException(status_code=400, detail="档位无效")
    note = body.dispute_note[:500]
    rows_to_create: list[tuple[str, list[str], str]] = []
    if body.items:
        seen: set[str] = set()
        for item in body.items:
            tid = str(item.trait_id or "").strip().upper()
            if not tid.startswith("T") or tid in seen:
                continue
            seen.add(tid)
            rationale = (item.reviewer_rationale or "")[:1024]
            rows_to_create.append((tid, list(item.evidence_positive or []), rationale))
    else:
        shared = list(body.evidence_positive or [])
        seen = set()
        for raw in body.trait_ids or []:
            tid = str(raw or "").strip().upper()
            if not tid.startswith("T") or tid in seen:
                continue
            seen.add(tid)
            rows_to_create.append((tid, shared, ""))
    if not rows_to_create:
        raise HTTPException(status_code=400, detail="请至少选择一个维度")
    created: list[str] = []
    for tid, evidence, rationale in rows_to_create:
        row = AnchorTraitReview(
            anchor_essay_id=anchor_id,
            reviewer_label=label,
            trait_id=tid,
            level=level,
            evidence_positive=evidence,
            reviewer_rationale=rationale,
            dispute_note=note,
        )
        db.add(row)
        created.append(tid)
    db.commit()
    return {"count": len(created), "trait_ids": created}


@router.delete("/anchor-essays/{anchor_id}/reviews/{review_id}")
def delete_anchor_trait_review(
    anchor_id: str,
    review_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.models.entities import AnchorEssay, AnchorTraitReview

    anchor = db.get(AnchorEssay, anchor_id)
    if not anchor:
        raise HTTPException(status_code=404, detail="锚作文不存在")
    row = db.get(AnchorTraitReview, review_id)
    if not row or row.anchor_essay_id != anchor_id:
        raise HTTPException(status_code=404, detail="标注记录不存在")
    db.delete(row)
    db.commit()
    return {"deleted": review_id}


# --- PRD V1 弱监督 + 主动学习（Phase 5） ---


@router.get("/weak-labels/export.jsonl")
def export_weak_labels_jsonl(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(5000, ge=1, le=20000),
) -> StreamingResponse:
    from app.services.weak_supervision_factory import export_weak_labels

    rows = export_weak_labels(db, limit=limit)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    body = "\n".join(lines) + ("\n" if lines else "")
    return StreamingResponse(
        iter([body]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=weak_labels.jsonl"},
    )


@router.get("/calibration/metrics")
def get_calibration_metrics(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    from app.services.trait_calibration_service import calibration_dashboard

    return calibration_dashboard(db)


@router.get("/weak-supervision/bundle")
def get_weak_supervision_bundle(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    question_id: str | None = None,
    limit: int = Query(5000, ge=1, le=20000),
) -> dict:
    from app.services.weak_supervision_v2_export import export_weak_supervision_bundle

    return export_weak_supervision_bundle(db, question_id=question_id, label_limit=limit)


@router.get("/questions/{question_id}/anchor-calibration")
def get_anchor_calibration(
    question_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.anchor_bradley_terry import anchor_calibration_summary

    if not db.get(Question, question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    return anchor_calibration_summary(db, question_id)


@router.post("/weak-labels/seed-counterexamples")
def seed_counterexample_weak_labels(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    question_id: str | None = None,
) -> dict:
    from app.services.weak_supervision_factory import ensure_counterexample_templates

    added = ensure_counterexample_templates(db, question_id=question_id)
    db.commit()
    return {"added": added}


@router.get("/active-learning/export.jsonl")
def export_active_learning_jsonl(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    status: str = Query("open"),
    limit: int = Query(2000, ge=1, le=10000),
) -> StreamingResponse:
    from app.models.entities import ActiveLearningPoolEntry

    q = db.query(ActiveLearningPoolEntry).order_by(ActiveLearningPoolEntry.priority.desc())
    if status:
        q = q.filter(ActiveLearningPoolEntry.status == status)
    rows = q.limit(limit).all()
    lines = [
        json.dumps(
            {
                "id": r.id,
                "reason": r.reason.value,
                "priority": r.priority,
                "status": r.status,
                "submission_id": r.submission_id,
                "question_id": r.question_id,
                "snapshot": r.snapshot,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            },
            ensure_ascii=False,
        )
        for r in rows
    ]
    body = "\n".join(lines) + ("\n" if lines else "")
    return StreamingResponse(
        iter([body]),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=active_learning_pool.jsonl"},
    )


@router.get("/active-learning/pool")
def list_active_learning_pool(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    status: str = Query("open"),
    limit: int = Query(200, ge=1, le=1000),
) -> list[dict]:
    from app.models.entities import ActiveLearningPoolEntry

    q = db.query(ActiveLearningPoolEntry).order_by(ActiveLearningPoolEntry.priority.desc())
    if status:
        q = q.filter(ActiveLearningPoolEntry.status == status)
    rows = q.limit(limit).all()
    return [
        {
            "id": r.id,
            "reason": r.reason.value,
            "priority": r.priority,
            "status": r.status,
            "submission_id": r.submission_id,
            "question_id": r.question_id,
            "snapshot": r.snapshot,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/pair-compare/tasks")
def create_pair_compare(
    body: PairCompareCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.trait_pair_compare import create_pair_compare_task

    try:
        task = create_pair_compare_task(
            db,
            question_id=body.question_id,
            submission_a_id=body.submission_a_id,
            submission_b_id=body.submission_b_id,
            trait_id=body.trait_id,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": task.id, "status": task.status.value}


@router.post("/pair-compare/tasks/{task_id}/complete")
def complete_pair_compare_task(
    task_id: str,
    body: PairCompareComplete,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.trait_pair_compare import complete_pair_compare

    try:
        task = complete_pair_compare(
            db,
            task_id,
            preferred_submission_id=body.preferred_submission_id,
            trait_id=body.trait_id,
            note=body.note,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": task.id, "status": task.status.value}


# --- 埋点查询（BE-608） ---


@router.get("/events")
def list_events(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(AnalyticsEvent).order_by(AnalyticsEvent.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "event_name": r.event_name,
            "user_id": r.user_id,
            "properties": r.properties,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
