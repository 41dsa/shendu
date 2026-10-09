"""标准生成输入指纹与 LLM 流水线缓存。"""

import hashlib
import os
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Question, StandardDocument, StandardPipelineCache
from app.schemas.standard_engine import (
    MaterialAnalysisSchema,
    QuestionStandardSchema,
    RubricStandardSchema,
)
from app.services.standard_engine.llm_json import validate_model


def standard_gen_cache_enabled() -> bool:
    return os.environ.get("STANDARD_GEN_CACHE", "1").lower() not in ("0", "false", "no")


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_content_hashes(db: Session, document_ids: list[str]) -> list[str]:
    hashes: list[str] = []
    for doc_id in sorted(document_ids):
        doc = db.get(StandardDocument, doc_id)
        content = (doc.content if doc else "") or ""
        hashes.append(_hash_text(content))
    return hashes


def compute_standard_input_fingerprint(
    *,
    question: Question,
    document_ids: list[str],
    document_hashes: list[str],
    gen_mode: str,
) -> str:
    parts = [
        question.id,
        (question.prompt or "").strip(),
        (question.material or "").strip()[:12000],
        str(question.score or 0),
        str(question.word_limit or 0),
        gen_mode,
        ",".join(sorted(document_ids)),
        ",".join(document_hashes),
    ]
    return _hash_text("\n---\n".join(parts))


def get_pipeline_cache(db: Session, fingerprint: str) -> StandardPipelineCache | None:
    return db.get(StandardPipelineCache, fingerprint)


def upsert_pipeline_cache(
    db: Session,
    *,
    fingerprint: str,
    question_id: str,
    gen_mode: str,
    source_job_id: str,
    bundle: dict[str, Any],
) -> None:
    row = db.get(StandardPipelineCache, fingerprint)
    if row:
        row.question_id = question_id
        row.gen_mode = gen_mode
        row.source_job_id = source_job_id
        row.bundle = bundle
    else:
        db.add(
            StandardPipelineCache(
                input_fingerprint=fingerprint,
                question_id=question_id,
                gen_mode=gen_mode,
                source_job_id=source_job_id,
                bundle=bundle,
            )
        )
    db.commit()


def build_cache_bundle(
    *,
    question_std: dict[str, Any],
    material_analysis: dict[str, Any],
    rubric_candidates: dict[str, Any],
    rubric_merged: dict[str, Any],
    validate_p05: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "question_std": question_std,
        "material_analysis": material_analysis,
        "rubric_candidates": rubric_candidates,
        "rubric_merged": rubric_merged,
    }
    if validate_p05:
        bundle["validate_p05"] = validate_p05
    return bundle


def restore_from_cache_bundle(bundle: dict[str, Any]) -> tuple[QuestionStandardSchema, MaterialAnalysisSchema, RubricStandardSchema, dict[str, Any]]:
    q_std = validate_model(QuestionStandardSchema, dict(bundle["question_std"]))  # type: ignore[arg-type]
    mat = validate_model(MaterialAnalysisSchema, dict(bundle["material_analysis"]))  # type: ignore[arg-type]
    rubric = validate_model(RubricStandardSchema, dict(bundle["rubric_merged"]))  # type: ignore[arg-type]
    rubric_debug = dict(bundle.get("rubric_candidates") or {})
    return q_std, mat, rubric, rubric_debug  # type: ignore[return-value]
