import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
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
from app.schemas.admin_research import AdminQuestionUpsert, GoldSampleCreate, PromptVersionCreate
from app.services.gold_service import regression_summary, run_gold_sample_sync
from app.services.events_service import track_event

router = APIRouter(prefix="/admin", tags=["admin-research"])


# --- 大作文题库 CRUD（BE-602） ---


@router.get("/questions")
def admin_list_questions(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = (
        db.query(Question)
        .filter(Question.id != USER_ESSAY_QUESTION_ID)
        .order_by(Question.title)
        .all()
    )
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
        }
        for r in rows
    ]


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
    row.title = body.title
    row.prompt = body.prompt
    row.material = body.material
    row.score = body.score
    row.word_limit = body.word_limit
    row.material_structured = {"genre": "essay", "word_min": body.word_min, "word_max": body.word_max}
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
    return {"id": row.id, "name": row.name, "content": row.content, "is_active": row.is_active}


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
