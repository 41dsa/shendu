"""AI 考试标准引擎 — Admin API（M1/M8 起步）。"""

import csv
import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
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
    EssayImportAudit,
    StandardGenerationJob,
    StandardGenerationJobStatus,
    StandardJobStep,
    User,
)
from app.schemas.standard_engine import (
    ExamStandardPublishRequest,
    JobRubricDraftPatch,
    LinkDocumentsRequest,
    StandardCardReviewRequest,
    StandardDocumentCreateRequest,
    StandardJobCreateRequest,
)
from app.services.standard_engine.draft_edit_service import patch_job_rubric_draft
from app.services.standard_engine.exam_standard_service import (
    get_active_exam_standard,
    list_exam_standards,
    publish_complete_exam_bundles,
    publish_exam_standard,
)
from app.services.standard_engine.structure_service import get_linked_document_ids
from app.services.standard_engine.ingest_service import ingest_uploaded_file, save_upload_bytes
from app.services.standard_engine.metrics_eval import evaluate_annotation_csv
from app.services.standard_engine.publish_service import PublishBlockedError, publish_standard_from_job, rollback_standard_version
from app.services.standard_engine.standard_card_review_service import (
    get_job_standard_card_v1,
    list_standard_card_review_queue,
    review_standard_card,
)
from app.services.standard_engine.standard_store import get_active_standard_row
from app.services.standard_engine.structure_service import (
    build_structured_essay,
    link_documents_to_question,
)
from app.worker.tasks import enqueue_standard_generation_job

router = APIRouter(prefix="/admin/standards", tags=["admin-standards"])

_ANNOTATION_CSV_ALLOWLIST = frozenset({"questions_for_labeling.csv", "annotation_template.csv"})


@router.get("/engine-config")
def get_standard_engine_config(_: User = Depends(require_admin)) -> dict:
    """运维：标准引擎与 PRD V1 相关开关（只读）。"""
    return {
        "standard_consensus_3model_enabled": bool(settings.standard_consensus_3model_enabled),
        "standard_consensus_min_score": float(settings.standard_consensus_min_score),
        "standard_publish_min_confidence": float(settings.standard_publish_min_confidence),
        "trait_llm_voting_enabled": bool(settings.trait_llm_voting_enabled),
        "weak_supervision_enabled": bool(settings.weak_supervision_enabled),
    }


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
    meta = dict(body.metadata or {})
    row = StandardDocument(
        title=body.title,
        source_level=SourceLevel(body.source_level),
        exam=body.exam,
        year=body.year,
        content=body.content,
        metadata_json=meta,
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
    doc_category: str = Form("reference"),
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
        doc_category=doc_category,
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
            "doc_category": (r.metadata_json or {}).get("doc_category"),
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
    question = db.get(Question, body.question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    document_ids = list(body.document_ids or [])
    if not document_ids:
        document_ids = get_linked_document_ids(question)
    job = StandardGenerationJob(
        question_id=body.question_id,
        created_by_user_id=admin.id,
        document_ids=document_ids,
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


class EssayItemsJsonImportBody(BaseModel):
    """Q-03：JSON 批量导入 EssayItem。"""

    source: str = "json"
    filename: str | None = None
    lock_a_fields: bool = True
    items: list[dict] = Field(default_factory=list)


@router.get("/essay-import-audits")
def list_essay_import_audits(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    rows = db.query(EssayImportAudit).order_by(EssayImportAudit.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "filename": r.filename,
            "item_count": r.item_count,
            "created_count": r.created_count,
            "updated_count": r.updated_count,
            "skipped_locked_count": r.skipped_locked_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/questions/import-csv")
async def import_questions_csv(
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """STD-210 / Q-03：批量导入大作文 CSV（EssayItem V1 + 审计）。"""
    from app.services.standard_engine.essay_item_import_service import import_essay_items

    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    result = import_essay_items(
        db,
        rows,
        source="csv",
        filename=file.filename,
        admin_user_id=admin.id,
        lock_a_fields=True,
    )
    return {
        "count": result.item_count,
        "question_ids": [ln.question_id for ln in result.lines],
        "created_count": result.created_count,
        "updated_count": result.updated_count,
        "skipped_locked_count": result.skipped_locked_count,
    }


@router.post("/questions/import-essay-items-json")
def import_essay_items_json(
    body: EssayItemsJsonImportBody,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.standard_engine.essay_item_import_service import import_essay_items

    result = import_essay_items(
        db,
        body.items,
        source=body.source,
        filename=body.filename,
        admin_user_id=admin.id,
        lock_a_fields=body.lock_a_fields,
    )
    return {
        "count": result.item_count,
        "question_ids": [ln.question_id for ln in result.lines],
        "created_count": result.created_count,
        "updated_count": result.updated_count,
        "skipped_locked_count": result.skipped_locked_count,
    }


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


@router.patch("/jobs/{job_id}/rubric-draft")
def patch_rubric_draft(
    job_id: str,
    body: JobRubricDraftPatch,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(status_code=400, detail="无修改内容")
    try:
        return patch_job_rubric_draft(db, job_id, patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exam-standards")
def list_exam_standard_rows(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    rows = list_exam_standards(db)
    return [
        {
            "id": r.id,
            "exam": r.exam,
            "year": r.year,
            "version": r.version,
            "status": r.status.value,
            "is_active": r.is_active,
            "question_count": (r.payload or {}).get("question_count"),
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in rows
    ]


@router.get("/exam-standards/active")
def get_active_exam_standard_row(
    exam: str = Query(...),
    year: int = Query(...),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    row = get_active_exam_standard(db, exam, year)
    if not row:
        raise HTTPException(status_code=404, detail="无生效考试级标准")
    return {
        "id": row.id,
        "exam": row.exam,
        "year": row.year,
        "version": row.version,
        "payload": row.payload,
        "published_at": row.published_at.isoformat() if row.published_at else None,
    }


@router.post("/exam-standards/publish-all")
def publish_all_exam_bundles(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    rows = publish_complete_exam_bundles(db)
    return {
        "count": len(rows),
        "bundles": [
            {"exam": r.exam, "year": r.year, "version": r.version, "question_count": (r.payload or {}).get("question_count")}
            for r in rows
        ],
    }


@router.post("/exam-standards/publish")
def publish_exam_standard_bundle(
    body: ExamStandardPublishRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        row = publish_exam_standard(
            db,
            exam=body.exam,
            year=body.year,
            essay_policy=body.essay_policy or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": row.id,
        "exam": row.exam,
        "year": row.year,
        "version": row.version,
        "question_count": (row.payload or {}).get("question_count"),
    }


@router.get("/standard-card-review-queue")
def standard_card_review_queue(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[dict]:
    """M-14：待教研审核的标准卡（validated 且 review_status≠published）。"""
    return list_standard_card_review_queue(db)


@router.get("/jobs/{job_id}/standard-card-v1")
def get_job_standard_card(job_id: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    job = db.get(StandardGenerationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return get_job_standard_card_v1(db, job_id)


@router.post("/jobs/{job_id}/standard-card-review")
def post_standard_card_review(
    job_id: str,
    body: StandardCardReviewRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = review_standard_card(
            db,
            job_id,
            action=body.action,
            admin_user_id=admin.id,
            note=body.note,
            dispute_marks=body.dispute_marks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if body.publish_after and body.action == "approve":
        try:
            row = publish_standard_from_job(db, job_id, force=False)
        except PublishBlockedError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"审核已通过但发布被拦截: {exc}",
            ) from exc
        result["published"] = True
        result["standard_version"] = row.version
        result["standard_id"] = row.id
    return result


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
