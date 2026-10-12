"""标准生成流水线（主流程 + 分步任务，无 LangGraph）。"""

import asyncio
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.standard_engine.confidence import aggregate_standard_confidence, confidence_band
from app.domain.standard_engine.reference_coverage import (
    coverage_ratio_from_p05,
    heuristic_reference_coverage_ratio,
)
from app.domain.standard_engine.validation import run_standard_validators
from app.models.entities import (
    CredentialRole,
    Question,
    StandardGenerationJob,
    StandardGenerationJobStatus,
    StandardJobStep,
)
from app.services.ai_client import get_credential
from app.services.standard_engine.ingest_service import load_document_texts
from app.services.standard_engine.annotation_bootstrap import sync_annotation_after_job
from app.services.standard_engine.input_cache import (
    build_cache_bundle,
    compute_standard_input_fingerprint,
    document_content_hashes,
    get_pipeline_cache,
    restore_from_cache_bundle,
    standard_gen_cache_enabled,
    upsert_pipeline_cache,
)
from app.services.standard_engine.llm_generate import (
    assess_reference_coverage_llm,
    build_loss_rules,
    generate_material_analysis_llm,
    generate_question_standard_llm,
    generate_rubric_llm,
)
from app.services.standard_engine.publish_service import try_auto_publish_after_validation
from app.services.standard_engine.structure_service import build_structured_essay
from app.services.standard_engine.stub_generate import (
    stub_material_analysis,
    stub_question_standard,
    stub_rubric_standard,
)
from app.config import settings
from app.services.point_pool_pipeline.build import (
    build_point_pool_bundle,
    build_point_pool_bundle_sync_stub,
    bundle_to_payload_dict,
)

STANDARD_PIPELINE_STEPS = [
    "ingest",
    "structured",
    "question_std",
    "material_analysis",
    "rubric_candidates",
    "rubric_merged",
    "loss_rules",
    "validate_p05",
    "point_pool_build",
    "validate",
    "publish",
]


def append_job_step(
    db: Session,
    job: StandardGenerationJob,
    step: str,
    payload: dict[str, Any],
    detail: str = "done",
) -> None:
    job.current_step = step
    db.add(
        StandardJobStep(
            job_id=job.id,
            step=step,
            detail=detail,
            payload=payload,
        )
    )
    db.commit()


def _use_llm(job: StandardGenerationJob, db: Session) -> bool:
    mode = os.environ.get("STANDARD_GEN_MODE", "auto").lower()
    if mode == "stub":
        return False
    if mode == "llm":
        return True
    if not job.created_by_user_id:
        return False
    cred = get_credential(db, job.created_by_user_id, CredentialRole.primary)
    return cred is not None


async def _run_pipeline_async(db: Session, job_id: str) -> None:
    job = db.get(StandardGenerationJob, job_id)
    if not job:
        return
    job.status = StandardGenerationJobStatus.running
    job.error_message = None
    db.commit()

    question = db.get(Question, job.question_id)
    if not question:
        job.status = StandardGenerationJobStatus.failed
        job.error_message = "题目不存在"
        job.finished_at = datetime.now(UTC)
        db.commit()
        return

    use_llm = _use_llm(job, db)
    cred = None
    if use_llm:
        cred = get_credential(db, job.created_by_user_id or "", CredentialRole.primary)
        if not cred:
            use_llm = False

    doc_ids = list(job.document_ids or [])
    doc_refs = load_document_texts(db, doc_ids)
    doc_excerpts = [d.get("content_excerpt") or "" for d in doc_refs if d.get("content_excerpt")]
    gen_mode = "llm" if use_llm else "stub"
    doc_hashes = document_content_hashes(db, doc_ids)
    input_fingerprint = compute_standard_input_fingerprint(
        question=question,
        document_ids=doc_ids,
        document_hashes=doc_hashes,
        gen_mode=gen_mode,
    )

    cache_row = None
    if use_llm and standard_gen_cache_enabled():
        cache_row = get_pipeline_cache(db, input_fingerprint)
    served_from_cache = cache_row is not None and bool(cache_row.bundle)

    append_job_step(
        db,
        job,
        "ingest",
        {
            "question_id": job.question_id,
            "document_ids": doc_ids,
            "documents": doc_refs,
            "mode": gen_mode,
            "input_fingerprint": input_fingerprint,
            "cache_hit": served_from_cache,
            "cache_source_job_id": cache_row.source_job_id if cache_row else None,
        },
    )

    essay = build_structured_essay(db, question)
    from app.services.standard_engine.question_parse import parse_essay_question_metadata

    structured_payload = {
        **essay.model_dump(),
        "parse": parse_essay_question_metadata(question),
    }
    append_job_step(db, job, "structured", structured_payload)

    user_id = job.created_by_user_id or ""
    cached_p05: dict[str, Any] | None = None
    rubric_candidates_payload: dict[str, Any] = {}

    if served_from_cache and cache_row:
        q_std, mat, rubric, rubric_debug = restore_from_cache_bundle(cache_row.bundle)
        append_job_step(db, job, "question_std", {**q_std.model_dump(), "cache_hit": True}, detail="cache_hit")
        append_job_step(db, job, "material_analysis", {**mat.model_dump(), "cache_hit": True}, detail="cache_hit")
        rubric_candidates_payload = dict(rubric_debug)
        append_job_step(
            db,
            job,
            "rubric_candidates",
            {**rubric_candidates_payload, "cache_hit": True},
            detail="cache_hit",
        )
        append_job_step(db, job, "rubric_merged", {**rubric.model_dump(), "cache_hit": True}, detail="cache_hit")
        cached_p05 = dict(cache_row.bundle.get("validate_p05") or {}) or None
    elif use_llm and cred:
        append_job_step(db, job, "question_std", {"status": "calling"}, detail="calling_llm")
        q_std = await generate_question_standard_llm(db, cred, essay, user_id=user_id, job_id=job.id)
        append_job_step(db, job, "question_std", q_std.model_dump())

        mat = await generate_material_analysis_llm(db, cred, essay, q_std, user_id=user_id, job_id=job.id)
        append_job_step(db, job, "material_analysis", mat.model_dump())

        rubric_debug, rubric = await generate_rubric_llm(
            db, cred, essay, q_std, mat, doc_excerpts, user_id=user_id, job_id=job.id
        )
        rubric_candidates_payload = {"candidates": rubric_debug.get("candidates") or []}
        append_job_step(db, job, "rubric_candidates", rubric_candidates_payload)
        append_job_step(db, job, "rubric_merged", rubric.model_dump())
    else:
        q_std = stub_question_standard(essay)
        append_job_step(db, job, "question_std", {**q_std.model_dump(), "source": "stub"})

        mat = stub_material_analysis(essay)
        append_job_step(db, job, "material_analysis", mat.model_dump())

        rubric = stub_rubric_standard(essay, q_std)
        rubric_candidates_payload = {"source": "stub"}
        append_job_step(db, job, "rubric_candidates", rubric_candidates_payload)
        append_job_step(db, job, "rubric_merged", rubric.model_dump())

    loss = build_loss_rules(rubric)
    rubric.loss_rules = loss
    append_job_step(db, job, "loss_rules", {"rules": [r.model_dump() for r in loss]})

    rubric_dict = rubric.model_dump()
    point_pools_payload: dict[str, Any] = {}
    if served_from_cache and cache_row and cache_row.bundle.get("point_pools"):
        point_pools_payload = dict(cache_row.bundle.get("point_pools") or {})
        append_job_step(db, job, "point_pool_build", {**point_pools_payload, "cache_hit": True}, detail="cache_hit")
    elif settings.point_pool_pipeline_enabled:
        themes = list(getattr(mat, "themes", None) or (mat.model_dump().get("themes") if mat else []) or [])
        focus_pts = list(q_std.focus_points or [])
        criteria_dicts = [c.model_dump() for c in rubric.criteria]
        if use_llm and cred:
            pp_bundle = await build_point_pool_bundle(
                db,
                question_id=job.question_id,
                prompt=essay.prompt,
                material=question.material,
                rubric_criteria=criteria_dicts,
                focus_points=focus_pts,
                themes=themes,
                reference_excerpts=doc_excerpts,
                user_id=user_id,
                job_id=job.id,
            )
        else:
            pp_bundle = build_point_pool_bundle_sync_stub(
                question_id=job.question_id,
                prompt=essay.prompt,
                material=question.material,
                rubric_criteria=criteria_dicts,
                focus_points=focus_pts,
                themes=themes,
            )
        point_pools_payload = bundle_to_payload_dict(pp_bundle)
        append_job_step(db, job, "point_pool_build", point_pools_payload)
    use_p05 = os.environ.get("STANDARD_USE_P05", "1").lower() not in ("0", "false", "no")
    ref_ratio: float
    p05_payload: dict[str, Any] | None = None
    if cached_p05:
        p05_payload = {**cached_p05, "source": cached_p05.get("source") or "cache", "cache_hit": True}
        ref_ratio = float(
            p05_payload.get("coverage_ratio")
            or heuristic_reference_coverage_ratio(rubric_dict, doc_excerpts)
        )
        p05_payload["coverage_ratio"] = ref_ratio
        append_job_step(db, job, "validate_p05", p05_payload, detail="cache_hit")
    elif use_llm and cred and use_p05 and doc_excerpts:
        p05_payload = await assess_reference_coverage_llm(
            db,
            cred,
            question_standard=q_std,
            rubric=rubric,
            reference_excerpts=doc_excerpts,
            user_id=user_id,
            job_id=job.id,
        )
        ref_ratio = coverage_ratio_from_p05(
            p05_payload,
            criteria_count=len(rubric.criteria),
        )
        p05_payload["coverage_ratio"] = ref_ratio
        p05_payload["source"] = "llm_p05"
        append_job_step(db, job, "validate_p05", p05_payload)
    else:
        ref_ratio = heuristic_reference_coverage_ratio(rubric_dict, doc_excerpts)
        p05_payload = {
            "source": "heuristic",
            "coverage_ratio": ref_ratio,
            "reference_excerpt_count": len(doc_excerpts),
        }
        append_job_step(db, job, "validate_p05", p05_payload)

    validation = run_standard_validators(
        question_standard=q_std.model_dump(),
        rubric=rubric_dict,
        prompt_text=essay.prompt,
        reference_coverage_ratio=ref_ratio,
    )
    validation["reference_coverage_detail"] = p05_payload
    agg_conf = aggregate_standard_confidence([c.model_dump() for c in rubric.criteria])
    validation["standard_confidence"] = agg_conf
    validation["confidence_band"] = confidence_band(agg_conf)
    append_job_step(db, job, "validate", validation)
    enriched = validation.get("enriched_rubric")
    if enriched:
        append_job_step(db, job, "rubric_merged", enriched, detail="enriched_contract")

    job.status = (
        StandardGenerationJobStatus.validated
        if validation.get("overall_passed")
        else StandardGenerationJobStatus.failed
    )
    if not validation.get("overall_passed"):
        job.error_message = "验证未通过: " + ",".join(validation.get("blocking_issues") or [])
    else:
        sync_annotation_after_job(
            db,
            question_id=job.question_id,
            question_standard=q_std.model_dump(),
            rubric=rubric_dict,
            title=question.title,
        )
        db.commit()
        published = try_auto_publish_after_validation(db, job.id)
        if published:
            append_job_step(
                db,
                job,
                "publish",
                {
                    "version": published.version,
                    "standard_id": published.id,
                    "auto": True,
                    "force": os.environ.get("STANDARD_AUTO_PUBLISH_FORCE", "0"),
                },
                detail="auto_publish",
            )
            db.refresh(job)
        elif os.environ.get("STANDARD_AUTO_PUBLISH", "0").lower() in ("1", "true", "yes"):
            append_job_step(
                db,
                job,
                "publish",
                {"auto": True, "skipped": True},
                detail="auto_publish_blocked",
            )
    if validation.get("overall_passed") and use_llm and not served_from_cache and standard_gen_cache_enabled():
        upsert_pipeline_cache(
            db,
            fingerprint=input_fingerprint,
            question_id=job.question_id,
            gen_mode=gen_mode,
            source_job_id=job.id,
            bundle=build_cache_bundle(
                question_std=q_std.model_dump(),
                material_analysis=mat.model_dump(),
                rubric_candidates=rubric_candidates_payload,
                rubric_merged=rubric.model_dump(),
                validate_p05=p05_payload,
                point_pools=point_pools_payload or None,
            ),
        )
    job.finished_at = datetime.now(UTC)
    db.commit()


def run_standard_generation_job(db: Session, job_id: str) -> None:
    try:
        asyncio.run(_run_pipeline_async(db, job_id))
    except Exception as exc:
        job = db.get(StandardGenerationJob, job_id)
        if job:
            job.status = StandardGenerationJobStatus.failed
            job.error_message = str(exc)[:500]
            job.finished_at = datetime.now(UTC)
            db.commit()
        raise
