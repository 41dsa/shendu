"""发布前 Rubric 草稿编辑（PDF-P4-01，大作文）。"""

from typing import Any

from sqlalchemy.orm import Session

from app.domain.standard_engine.confidence import aggregate_standard_confidence, confidence_band
from app.domain.standard_engine.validation import run_standard_validators
from app.models.entities import Question, StandardGenerationJob, StandardGenerationJobStatus, StandardJobStep
from app.schemas.standard_engine import RubricStandardSchema
from app.services.standard_engine.llm_json import validate_model
from app.services.standard_engine.publish_service import _latest_step_payload
from app.services.standard_engine.structure_service import build_structured_essay


def _latest_rubric_payload(db: Session, job_id: str) -> dict[str, Any]:
    return _latest_step_payload(db, job_id, "rubric_merged")


def patch_job_rubric_draft(db: Session, job_id: str, rubric_patch: dict[str, Any]) -> dict[str, Any]:
    job = db.get(StandardGenerationJob, job_id)
    if not job:
        raise ValueError("任务不存在")
    if job.status not in (
        StandardGenerationJobStatus.validated,
        StandardGenerationJobStatus.failed,
    ):
        raise ValueError("仅 validated / failed 任务可编辑 Rubric 草稿")

    current = dict(_latest_rubric_payload(db, job_id))
    merged = {**current, **rubric_patch}
    if rubric_patch.get("criteria") is not None:
        merged["criteria"] = rubric_patch["criteria"]
    if rubric_patch.get("dimensions") is not None:
        merged["dimensions"] = rubric_patch["dimensions"]
    merged["question_id"] = job.question_id

    rubric = validate_model(RubricStandardSchema, merged)  # type: ignore[assignment]
    rubric_dict = rubric.model_dump()

    db.add(
        StandardJobStep(
            job_id=job.id,
            step="rubric_merged",
            detail="draft_edit",
            payload=rubric_dict,
        )
    )

    q_std = _latest_step_payload(db, job.id, "question_std")
    question = db.get(Question, job.question_id)
    if not question:
        raise ValueError("题目不存在")
    essay = build_structured_essay(db, question)

    p05 = _latest_step_payload(db, job.id, "validate_p05")
    ref_ratio = float(p05.get("coverage_ratio") or 0.0)

    validation = run_standard_validators(
        question_standard=q_std,
        rubric=rubric_dict,
        prompt_text=essay.prompt,
        reference_coverage_ratio=ref_ratio,
    )
    validation["reference_coverage_detail"] = p05
    agg_conf = aggregate_standard_confidence(rubric_dict.get("criteria") or [])
    validation["standard_confidence"] = agg_conf
    validation["confidence_band"] = confidence_band(agg_conf)

    db.add(
        StandardJobStep(
            job_id=job.id,
            step="validate",
            detail="after_draft_edit",
            payload=validation,
        )
    )

    job.status = (
        StandardGenerationJobStatus.validated
        if validation.get("overall_passed")
        else StandardGenerationJobStatus.failed
    )
    if validation.get("overall_passed"):
        job.error_message = None
    else:
        job.error_message = "验证未通过: " + ",".join(validation.get("blocking_issues") or [])

    db.commit()
    return {"rubric_standard": rubric_dict, "validation": validation, "job_status": job.status.value}
