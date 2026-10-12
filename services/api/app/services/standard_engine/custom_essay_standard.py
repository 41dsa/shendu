"""用户自备批改：按题干/材料走标准生产流水线（缓存复用）。"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.domain.standard_engine.validation import run_standard_validators
from app.models.entities import CredentialRole, StandardPipelineCache
from app.models.entities import Question, Submission
from app.schemas.standard_engine import EssayQuestionSchema, RubricStandardSchema
from app.services.ai_client import get_credential
from app.services.standard_engine.input_cache import build_cache_bundle, upsert_pipeline_cache
from app.services.standard_engine.llm_generate import (
    build_loss_rules,
    generate_material_analysis_llm,
    generate_question_standard_llm,
    generate_rubric_llm,
)
from app.services.standard_engine.stub_generate import (
    stub_material_analysis,
    stub_question_standard,
    stub_rubric_standard,
)


def custom_essay_standard_enabled() -> bool:
    return bool(settings.custom_essay_standard_engine_enabled)


def _resolve_gen_mode() -> str:
    raw = (settings.custom_essay_standard_mode or "auto").strip().lower()
    if raw in ("stub", "llm"):
        return raw
    return "auto"


def custom_input_fingerprint(
    *,
    prompt: str,
    material: str | None,
    score: int,
    word_max: int,
    gen_mode: str,
) -> str:
    parts = [
        "custom_essay_v1",
        gen_mode,
        str(score),
        str(word_max),
        prompt.strip()[:8000],
        (material or "").strip()[:12000],
    ]
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()


def essay_schema_from_submission(submission: Submission, question: Question) -> EssayQuestionSchema:
    prompt = (submission.user_prompt or "").strip()
    material = submission.user_material if submission.user_material is not None else ""
    meta = question.material_structured or {}
    return EssayQuestionSchema(
        question_id=USER_ESSAY_QUESTION_ID,
        prompt=prompt,
        requirements=prompt,
        word_min=int(meta.get("word_min") or 800),
        word_max=int(meta.get("word_max") or question.word_limit or 1200),
        score=int(question.score or 40),
        material_optional=(material or "").strip(),
        exam="用户自备",
        year=None,
    )


def _build_stub_bundle(essay: EssayQuestionSchema) -> dict[str, Any]:
    q_std = stub_question_standard(essay)
    mat = stub_material_analysis(essay)
    rubric = stub_rubric_standard(essay, q_std)
    loss = build_loss_rules(rubric)
    rubric.loss_rules = loss
    rubric_dict = rubric.model_dump()
    validation = run_standard_validators(
        question_standard=q_std.model_dump(),
        rubric=rubric_dict,
        prompt_text=essay.prompt,
        reference_coverage_ratio=1.0 if not essay.material_optional.strip() else 0.9,
    )
    if validation.get("enriched_rubric"):
        rubric_dict = validation["enriched_rubric"]
        rubric = RubricStandardSchema.model_validate(rubric_dict)
    return build_cache_bundle(
        question_std=q_std.model_dump(),
        material_analysis=mat.model_dump(),
        rubric_candidates={"source": "custom_essay_stub"},
        rubric_merged=rubric.model_dump(),
        validate_p05={"source": "custom_essay", "coverage_ratio": validation.get("checks", [{}])[1].get("coverage_ratio", 1.0)},
    )


async def _build_llm_bundle(
    db: Session,
    essay: EssayQuestionSchema,
    *,
    user_id: str,
    job_id: str,
) -> dict[str, Any]:
    cred = get_credential(db, user_id, CredentialRole.primary)
    if not cred:
        return _build_stub_bundle(essay)
    q_std = await generate_question_standard_llm(db, cred, essay, user_id=user_id, job_id=job_id)
    mat = await generate_material_analysis_llm(db, cred, essay, q_std, user_id=user_id, job_id=job_id)
    rubric_debug, rubric = await generate_rubric_llm(
        db, cred, essay, q_std, mat, [], user_id=user_id, job_id=job_id
    )
    loss = build_loss_rules(rubric)
    rubric.loss_rules = loss
    rubric_dict = rubric.model_dump()
    validation = run_standard_validators(
        question_standard=q_std.model_dump(),
        rubric=rubric_dict,
        prompt_text=essay.prompt,
        reference_coverage_ratio=0.9,
    )
    if validation.get("enriched_rubric"):
        rubric_dict = validation["enriched_rubric"]
        rubric = RubricStandardSchema.model_validate(rubric_dict)
    return build_cache_bundle(
        question_std=q_std.model_dump(),
        material_analysis=mat.model_dump(),
        rubric_candidates={"candidates": rubric_debug.get("candidates") or [], "source": "custom_essay_llm"},
        rubric_merged=rubric.model_dump(),
        validate_p05={"source": "custom_essay_llm", "coverage_ratio": 0.9},
    )


def bundle_to_grading_payload(bundle: dict[str, Any], *, fingerprint: str, gen_mode: str) -> dict[str, Any]:
    rubric = dict(bundle.get("rubric_merged") or {})
    loss_rules = list(rubric.get("loss_rules") or [])
    return {
        "question_id": USER_ESSAY_QUESTION_ID,
        "question_standard": bundle.get("question_std") or {},
        "material_analysis": bundle.get("material_analysis") or {},
        "rubric_standard": rubric,
        "loss_rules": loss_rules,
        "_meta": {
            "version": 1,
            "custom": True,
            "fingerprint": fingerprint[:16],
            "gen_mode": gen_mode,
            "source": "custom_essay_standard_engine",
        },
    }


def get_cached_custom_payload(
    db: Session,
    submission: Submission,
    question: Question,
) -> dict[str, Any] | None:
    if not (submission.user_prompt or "").strip():
        return None
    essay = essay_schema_from_submission(submission, question)
    for mode in ("stub", "llm"):
        fp = custom_input_fingerprint(
            prompt=essay.prompt,
            material=essay.material_optional,
            score=essay.score,
            word_max=essay.word_max,
            gen_mode=mode,
        )
        row = db.get(StandardPipelineCache, fp)
        if row and row.bundle:
            return bundle_to_grading_payload(row.bundle, fingerprint=fp, gen_mode=row.gen_mode or mode)
    return None


async def ensure_custom_essay_standard(
    db: Session,
    submission: Submission,
    question: Question,
    *,
    user_id: str,
    grading_job_id: str,
) -> dict[str, Any] | None:
    """批改前确保自备题已有标准流水线产物（命中缓存则跳过 LLM）。"""
    if not custom_essay_standard_enabled():
        return None
    if not (submission.user_prompt or "").strip():
        return None

    essay = essay_schema_from_submission(submission, question)
    mode = _resolve_gen_mode()
    if mode == "auto":
        mode = "llm" if get_credential(db, user_id, CredentialRole.primary) else "stub"

    fingerprint = custom_input_fingerprint(
        prompt=essay.prompt,
        material=essay.material_optional,
        score=essay.score,
        word_max=essay.word_max,
        gen_mode=mode,
    )
    existing = db.get(StandardPipelineCache, fingerprint)
    if existing and existing.bundle:
        return bundle_to_grading_payload(existing.bundle, fingerprint=fingerprint, gen_mode=existing.gen_mode or mode)

    if mode == "llm":
        bundle = await _build_llm_bundle(db, essay, user_id=user_id, job_id=grading_job_id)
    else:
        bundle = _build_stub_bundle(essay)

    upsert_pipeline_cache(
        db,
        fingerprint=fingerprint,
        question_id=USER_ESSAY_QUESTION_ID,
        gen_mode=mode,
        source_job_id=grading_job_id,
        bundle=bundle,
    )
    return bundle_to_grading_payload(bundle, fingerprint=fingerprint, gen_mode=mode)
