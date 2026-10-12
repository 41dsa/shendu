from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.domain.point_pool.consensus import (
    compute_point_confidence,
    evidence_strength_from_source,
    merge_vote_results,
    passes_consensus,
    position_weight_from_para,
)
from app.models.entities import CredentialRole, UserProviderCredential
from app.schemas.point_pool import ExamLevelId
from app.services.ai_client import AiCallError, chat_completion_json, get_credential
from app.services.point_pool_pipeline.l1_candidates import extract_candidates_l1


async def review_candidates_heuristic(
    candidates: list[dict[str, Any]],
    *,
    reviewer: str,
    level_id: ExamLevelId,
) -> dict[str, Any]:
    points: list[dict[str, Any]] = []
    for c in candidates:
        text = str(c.get("text") or "")
        accept = len(text) >= 6
        if level_id == "provincial" and c.get("extraction_method", "").startswith("structure_对策"):
            accept = accept and len(text) >= 10
        if level_id == "enforcement" and "依法" not in text and "服务" not in text:
            accept = accept and c.get("point_type") != "theme"
        points.append(
            {
                "text": text,
                "accept": accept,
                "keywords": c.get("keywords") or [],
                "source_para": c.get("source_para") or [],
                "point_type": c.get("point_type") or "sub",
                "reviewer": reviewer,
            }
        )
    return {"reviewer": reviewer, "points": points}


async def review_candidates_llm(
    db: Session,
    cred: UserProviderCredential,
    candidates: list[dict[str, Any]],
    *,
    reviewer: str,
    level_id: ExamLevelId,
    user_id: str,
    job_id: str,
) -> dict[str, Any]:
    subset = candidates[:40]
    system = (
        "你是申论采分点评审员。输入为候选采分点 JSON 列表。"
        "仅输出 JSON：{\"points\":[{\"text\":string,\"accept\":boolean,\"keywords\":[string],"
        "\"point_type\":\"main\"|\"sub\"|\"evidence\"}]}"
        f"考试级别={level_id}。accept 表示是否应进入点池。"
    )
    user = json.dumps({"candidates": subset, "reviewer": reviewer}, ensure_ascii=False)
    try:
        raw, _usage = await chat_completion_json(cred, system, user)
        data = json.loads(raw)
        points = data.get("points") or []
        for p in points:
            p["reviewer"] = reviewer
        return {"reviewer": reviewer, "points": points}
    except (AiCallError, json.JSONDecodeError):
        return await review_candidates_heuristic(candidates, reviewer=reviewer, level_id=level_id)


async def run_l2_consensus(
    db: Session,
    *,
    candidates: list[dict[str, Any]],
    level_id: ExamLevelId,
    material_paras: list[dict[str, Any]],
    user_id: str | None,
    job_id: str,
) -> list[dict[str, Any]]:
    votes: list[dict[str, Any]] = []
    votes.append(await review_candidates_heuristic(candidates, reviewer="heuristic", level_id=level_id))

    if user_id:
        cred_p = get_credential(db, user_id, CredentialRole.primary)
        if cred_p:
            votes.append(
                await review_candidates_llm(
                    db, cred_p, candidates, reviewer="primary", level_id=level_id, user_id=user_id, job_id=job_id
                )
            )
        cred_c = get_credential(db, user_id, CredentialRole.consensus)
        if cred_c and (not cred_p or cred_c.id != cred_p.id):
            votes.append(
                await review_candidates_llm(
                    db, cred_c, candidates, reviewer="consensus", level_id=level_id, user_id=user_id, job_id=job_id
                )
            )
        cred_r = get_credential(db, user_id, CredentialRole.reviewer)
        if cred_r and cred_r.id not in {getattr(cred_p, "id", None), getattr(cred_c, "id", None)}:
            votes.append(
                await review_candidates_llm(
                    db, cred_r, candidates, reviewer="reviewer", level_id=level_id, user_id=user_id, job_id=job_id
                )
            )

    merged = merge_vote_results(votes, min_votes=1)
    total_paras = len(material_paras)
    out: list[dict[str, Any]] = []
    for m in merged:
        ptype = str(m.get("point_type") or "sub")
        accept = int(m.get("accept_votes") or 0)
        total = int(m.get("total_votes") or 1)
        if not passes_consensus(ptype, accept, total):
            continue
        src = list(m.get("source_para") or [])
        conf = compute_point_confidence(
            consensus=accept / max(total, 1),
            evidence_strength=evidence_strength_from_source(src, in_material=bool(src)),
            position_weight=position_weight_from_para(src[0] if src else 0, total_paras=total_paras),
        )
        out.append({**m, "confidence": conf, "consensus_votes": accept, "consensus_total": total})
    return out


def build_l1_for_level(
    *,
    prompt: str,
    material_paras: list[dict[str, Any]],
    rubric_criteria: list[dict[str, Any]],
    focus_points: list[str],
    themes: list[str],
    level_id: ExamLevelId,
    reference_excerpts: list[str] | None,
) -> list[dict[str, Any]]:
    return extract_candidates_l1(
        prompt=prompt,
        material_paras=material_paras,
        rubric_criteria=rubric_criteria,
        focus_points=focus_points,
        themes=themes,
        level_id=level_id,
        reference_excerpts=reference_excerpts,
    )
