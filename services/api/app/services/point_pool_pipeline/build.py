"""点池构建流水线编排（L0→L3，L4 为离线审计）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.point_pool import ExamLevelId, PointPoolBundleSchema, PointPoolSchema
from app.services.point_pool_pipeline.l0_material import segment_material
from app.models.entities import CredentialRole
from app.services.ai_client import get_credential
from app.services.point_pool_pipeline.l1_llm_roles import extract_llm_role_candidates
from app.services.point_pool_pipeline.l2_consensus import build_l1_for_level, run_l2_consensus
from app.services.point_pool_pipeline.l3_atomic import build_point_pool_document

PIPELINE_VERSION = "1.0.0"
ALL_LEVELS: tuple[ExamLevelId, ...] = ("provincial", "municipal", "enforcement")


async def build_point_pool_bundle(
    db: Session,
    *,
    question_id: str,
    prompt: str,
    material: str | None,
    rubric_criteria: list[dict[str, Any]],
    focus_points: list[str],
    themes: list[str],
    reference_excerpts: list[str] | None,
    user_id: str | None,
    job_id: str,
) -> PointPoolBundleSchema:
    paras = segment_material(material)
    pools: dict[str, PointPoolSchema] = {}
    for level_id in ALL_LEVELS:
        l1 = build_l1_for_level(
            prompt=prompt,
            material_paras=paras,
            rubric_criteria=rubric_criteria,
            focus_points=focus_points,
            themes=themes,
            level_id=level_id,
            reference_excerpts=reference_excerpts,
        )
        if user_id:
            cred = get_credential(db, user_id, CredentialRole.primary)
            if cred:
                material_excerpt = "\n".join(p["text"] for p in paras[:12])
                l1.extend(
                    await extract_llm_role_candidates(
                        db,
                        cred,
                        prompt=prompt,
                        material_excerpt=material_excerpt,
                        level_id=level_id,
                        user_id=user_id,
                        job_id=job_id,
                    )
                )
        l2 = await run_l2_consensus(
            db,
            candidates=l1,
            level_id=level_id,
            material_paras=paras,
            user_id=user_id,
            job_id=job_id,
        )
        pool = build_point_pool_document(
            question_id=question_id,
            level_id=level_id,
            merged_points=l2,
            metadata={"l1_count": len(l1), "l2_count": len(l2), "material_paras": len(paras)},
        )
        pools[level_id] = pool

    return PointPoolBundleSchema(
        provincial=pools.get("provincial"),
        municipal=pools.get("municipal"),
        enforcement=pools.get("enforcement"),
        pipeline_version=PIPELINE_VERSION,
        built_at=datetime.now(UTC).isoformat(),
    )


def bundle_to_payload_dict(bundle: PointPoolBundleSchema) -> dict[str, Any]:
    out: dict[str, Any] = {
        "pipeline_version": bundle.pipeline_version,
        "built_at": bundle.built_at,
    }
    for level in ALL_LEVELS:
        pool = getattr(bundle, level)
        if pool:
            out[level] = pool.model_dump()
    return out


def build_point_pool_bundle_sync_stub(
    *,
    question_id: str,
    prompt: str,
    material: str | None,
    rubric_criteria: list[dict[str, Any]],
    focus_points: list[str],
    themes: list[str],
) -> PointPoolBundleSchema:
    """无 DB/LLM 的纯启发式构建（脚本与 stub 模式）。"""
    from app.services.point_pool_pipeline.l3_atomic import build_point_pool_document
    from app.services.point_pool_pipeline.l1_candidates import extract_candidates_l1

    paras = segment_material(material)
    pools: dict[str, PointPoolSchema] = {}
    for level_id in ALL_LEVELS:
        l1 = extract_candidates_l1(
            prompt=prompt,
            material_paras=paras,
            rubric_criteria=rubric_criteria,
            focus_points=focus_points,
            themes=themes,
            level_id=level_id,
            reference_excerpts=None,
        )
        pseudo = [
            {
                **c,
                "confidence": 0.72,
                "consensus_votes": 2,
                "consensus_total": 3,
                "accept_votes": 2,
                "total_votes": 3,
            }
            for c in l1
        ]
        pool = build_point_pool_document(
            question_id=question_id,
            level_id=level_id,
            merged_points=pseudo,
            metadata={"mode": "stub", "l1_count": len(l1)},
        )
        pools[level_id] = pool
    return PointPoolBundleSchema(
        provincial=pools["provincial"],
        municipal=pools["municipal"],
        enforcement=pools["enforcement"],
        pipeline_version=PIPELINE_VERSION,
        built_at=datetime.now(UTC).isoformat(),
    )
