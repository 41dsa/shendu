"""AI 考试标准引擎 — Admin API（M1/M8 起步）。"""

import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import require_admin
from app.models.entities import (
    ExamQuestionStandard,
    ExamQuestionStandardStatus,
    Question,
    SourceLevel,
    StandardDocument,
    StandardGenerationJob,
    StandardGenerationJobStatus,
    StandardJobStep,
    User,
)
from app.schemas.standard_engine import (
    LinkDocumentsRequest,
    StandardDocumentCreateRequest,
    StandardJobCreateRequest,
)
from app.services.standard_engine.ingest_service import ingest_uploaded_file, save_upload_bytes
from app.services.standard_engine.metrics_eval import evaluate_annotation_csv
from app.services.standard_engine.publish_service import PublishBlockedError, publish_standard_from_job, rollback_standard_version
from app.services.standard_engine.standard_store import get_active_standard_row
from app.services.standard_engine.structure_service import (
    build_structured_essay,
    link_documents_to_question,
    upsert_question_from_row,
)
from app.worker.tasks import enqueue_standard_generation_job

router = APIRouter(prefix="/admin/standards", tags=["admin-standards"])

_ANNOTATION_CSV_ALLOWLIST = frozenset({"questions_for_labeling.csv", "annotation_template.csv"})


def _summarize_jobs_steps(db: Session, job_ids: list[str]) -> dict[str, dict]:
    if not job_ids:
        return {}
    steps = (
        db.query(StandardJobStep)
        .filter(
            StandardJobStep.job_id.in_(job_ids),
            StandardJobStep.step.in_(("ingest", "validate", "rubric_candidates")),
        )
        .order_by(StandardJobStep.created_at.asc())
        .all()
    )
    out: dict[str, dict] = {jid: {} for jid in job_ids}
    for step in steps:
        payload = dict(step.payload or {})
        if step.step == "ingest":
            out[step.job_id]["gen_mode"] = payload.get("mode")
            out[step.job_id]["cache_hit"] = bool(payload.get("cache_hit"))
        elif step.step == "validate":
            out[step.job_id]["standard_confidence"] = payload.get("standard_confidence")
            out[step.job_id]["validation_passed"] = payload.get("overall_passed")
        elif step.step == "rubric_candidates":
            if payload.get("model_agreement") is not None:
                out[step.job_id]["model_agreement"] = payload.get("model_agreement")
    return out


@router.get("/annotation-metrics")
def get_annotation_metrics(
    file: str = Query("questions_for_labeling.csv", description="annotation 目录下 CSV 文件名"),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if file not in _ANNOTATION_CSV_ALLOWLIST:
        raise HTTPException(status_code=400, detail="不允许的文件名")
    path = settings.standards_annotation_path / file
    try:
        return evaluate_annotation_csv(db, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/documents")
def create_document(
    body: StandardDocumentCreateRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = StandardDocument(
        title=body.title,
        source_level=SourceLevel(body.source_level),
        exam=body.exam,
        year=body.year,
        content=body.content,
        metadata_json=body.metadata,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "title": row.title, "source_level": row.source_level.value}


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    source_level: str = Form("B"),
    exam: str = Form(""),
    year: int | None = Form(None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """STD-203：上传原始文件，解析后写入 standard_documents。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 20MB")
    path = save_upload_bytes(file.filename, data)
    row = ingest_uploaded_file(
        db,
        path=path,
        title=title or file.filename,
        source_level=SourceLevel(source_level),
        exam=exam,
        year=year,
    )
    meta = row.metadata_json or {}
    return {
        "id": row.id,
        "title": row.title,
        "source_level": row.source_level.value,
        "parse_quality": meta.get("parse_quality"),
        "parse_error": meta.get("parse_error"),
        "content_length": len(row.content or ""),
    }


@router.get("/documents")
def list_documents(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(StandardDocument).order_by(StandardDocument.created_at.desc()).limit(200).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "source_level": r.source_level.value,
            "exam": r.exam,
            "year": r.year,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/jobs")
def create_standard_job(
    body: StandardJobCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not db.get(Question, body.question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    job = StandardGenerationJob(
        question_id=body.question_id,
        created_by_user_id=admin.id,
        document_ids=body.document_ids,
        status=StandardGenerationJobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_standard_generation_job(job.id)
    return {"id": job.id, "question_id": job.question_id, "status": job.status.value}


@router.get("/jobs")
def list_standard_jobs(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(StandardGenerationJob).order_by(StandardGenerationJob.created_at.desc()).limit(100).all()
    summaries = _summarize_jobs_steps(db, [r.id for r in rows])
    return [
        {
            "id": r.id,
            "question_id": r.question_id,
            "status": r.status.value,
            "current_step": r.current_step,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            **summaries.get(r.id, {}),
        }
        for r in rows
    ]


@router.get("/jobs/{job_id}")
def get_standard_job(job_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    job = db.get(StandardGenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    steps = (
        db.query(StandardJobStep)
        .filter(StandardJobStep.job_id == job_id)
        .order_by(StandardJobStep.created_at.asc())
        .all()
    )
    return {
        "id": job.id,
        "question_id": job.question_id,
        "status": job.status.value,
        "current_step": job.current_step,
        "error_message": job.error_message,
        "document_ids": job.document_ids,
        "steps": [
            {
                "step": s.step,
                "detail": s.detail,
                "payload": s.payload,
                "at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in steps
        ],
    }


@router.get("/questions/{question_id}/structured")
def get_structured_question(
    question_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """STD-206：输出 EssayQuestion 结构化视图。"""
    question = db.get(Question, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    essay = build_structured_essay(db, question)
    return essay.model_dump()


@router.post("/questions/{question_id}/link-documents")
def link_question_documents(
    question_id: str,
    body: LinkDocumentsRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        question = link_documents_to_question(db, question_id, body.document_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    essay = build_structured_essay(db, question)
    return {"question_id": question_id, "essay": essay.model_dump()}


@router.post("/questions/import-csv")
async def import_questions_csv(
    file: UploadFile = File(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """STD-210：批量导入大作文 CSV。"""
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    ids: list[str] = []
    for row in reader:
        q = upsert_question_from_row(db, row)
        ids.append(q.id)
    return {"count": len(ids), "question_ids": ids}


@router.get("/questions/{question_id}/active")
def get_active_standard(
    question_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = get_active_standard_row(db, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="无已发布标准")
    return {
        "question_id": question_id,
        "version": row.version,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "payload": row.payload,
        "validation_result": row.validation_result,
    }


@router.get("/questions/{question_id}/versions")
def list_standard_versions(
    question_id: str,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = (
        db.query(ExamQuestionStandard)
        .filter(ExamQuestionStandard.question_id == question_id)
        .order_by(ExamQuestionStandard.version.desc())
        .all()
    )
    return [
        {
            "version": r.version,
            "status": r.status.value,
            "is_active": r.is_active,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in rows
    ]


@router.post("/jobs/{job_id}/publish")
def publish_job_standard(
    job_id: str,
    force: bool = False,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        row = publish_standard_from_job(db, job_id, force=force)
    except PublishBlockedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "standard_id": row.id,
        "question_id": row.question_id,
        "version": row.version,
        "validation_result": row.validation_result,
    }


@router.post("/questions/{question_id}/rollback")
def rollback_standard(
    question_id: str,
    version: int = Query(..., ge=1),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        row = rollback_standard_version(db, question_id, version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"question_id": question_id, "active_version": row.version}
