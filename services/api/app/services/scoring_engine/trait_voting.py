"""PRD V1：Trait 多模型投票（仅等级 + 原文证据，禁止输出总分）。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.trait_definitions import TraitLevel
from app.domain.scoring_engine.trait_vote_merge import merge_trait_level_votes
from app.models.entities import CredentialRole, UserProviderCredential
from app.services.ai_client import AiCallError, chat_completion_json, get_credential
from app.services.essay_context import EssayGradingContext

TRAIT_VOTE_PROMPT = """你是申论大作文 Trait 诊断员。仅根据题干与用户作文输出 JSON，禁止给出 total_score 或任何卷面总分。
{
  "traits": [
    {
      "trait_id": "T1"|"T2"|...|"T8",
      "level": "L0"|"L1"|"L2"|"L3"|"L4",
      "evidence_positive": [string],
      "evidence_negative": [string],
      "evidence_missing": [string]
    }
  ]
}
规则：evidence 必须是作文原文连续摘录；T2/T6/T7 为 C 档仍须给 level 但标注为诊断；不得编造未出现的句子。"""


def _parse_traits(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in raw.get("traits") or []:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("trait_id") or "").strip().upper()
        if not tid.startswith("T"):
            continue
        level = str(row.get("level") or "L2").upper()
        if level not in ("L0", "L1", "L2", "L3", "L4"):
            level = "L2"
        out[tid] = {
            "level": level,
            "evidence_positive": row.get("evidence_positive") or [],
            "evidence_negative": row.get("evidence_negative") or [],
            "evidence_missing": row.get("evidence_missing") or [],
        }
    return out


async def _one_vote(
    db: Session,
    cred: UserProviderCredential,
    user_prompt: str,
    *,
    model_label: str,
) -> dict[str, dict[str, Any]]:
    raw, _usage = await chat_completion_json(cred, TRAIT_VOTE_PROMPT, user_prompt)
    parsed = _parse_traits(json.loads(raw))
    for tid in parsed:
        parsed[tid]["model"] = model_label
    return parsed


def _distinct_voting_models(
    db: Session,
    user_id: str,
) -> list[tuple[UserProviderCredential, str]]:
    """primary → consensus → reviewer，去重；不足 min_models 时用 primary 重复补齐。"""
    seen: set[int] = set()
    models: list[tuple[UserProviderCredential, str]] = []
    for role, label in (
        (CredentialRole.primary, "primary"),
        (CredentialRole.consensus, "consensus"),
        (CredentialRole.reviewer, "reviewer"),
    ):
        cred = get_credential(db, user_id, role)
        if cred and cred.id not in seen:
            seen.add(cred.id)
            models.append((cred, label))
    if not models:
        return []
    target = max(1, min(int(settings.trait_llm_voting_min_models), 3))
    while len(models) < target:
        base_cred, base_label = models[0]
        models.append((base_cred, f"{base_label}_repeat_{len(models)}"))
    return models[:target]


async def collect_trait_votes(
    db: Session,
    *,
    user_id: str,
    ctx: EssayGradingContext,
    essay: str,
    base_diagnostics: list[dict[str, Any]],
) -> tuple[dict[str, tuple[TraitLevel, float, list[dict]]], float, dict[str, dict[str, Any]]]:
    """
    返回 (trait_id -> (merged_level, spread, vote_rows), max_spread, llm_evidence_by_trait)。
    失败时返回空 dict。
    """
    if not settings.trait_llm_voting_enabled:
        return {}, 0.0, {}

    models = _distinct_voting_models(db, user_id)
    if not models:
        return {}, 0.0, {}

    payload = {
        "prompt": ctx.prompt[:2000],
        "reference_material": (ctx.reference_material or "")[:2000],
        "user_essay": essay[:8000],
        "rule_baseline_traits": [
            {"trait_id": d.get("trait_id"), "level": d.get("level")} for d in base_diagnostics
        ],
    }
    user_prompt = json.dumps(payload, ensure_ascii=False)

    votes_by_trait: dict[str, list[TraitLevel]] = {f"T{i}": [] for i in range(1, 9)}
    vote_rows_by_trait: dict[str, list[dict]] = {f"T{i}": [] for i in range(1, 9)}
    evidence_by_trait: dict[str, dict[str, list[Any]]] = {f"T{i}": {
        "evidence_positive": [],
        "evidence_negative": [],
        "evidence_missing": [],
    } for i in range(1, 9)}

    for cred, label in models:
        try:
            parsed = await _one_vote(db, cred, user_prompt, model_label=label)
        except (AiCallError, json.JSONDecodeError, TypeError):
            continue
        for tid, row in parsed.items():
            if tid not in votes_by_trait:
                continue
            votes_by_trait[tid].append(row["level"])  # type: ignore[arg-type]
            vote_rows_by_trait[tid].append(
                {
                    "model": label,
                    "level": row["level"],
                    "role": "weak_label",
                }
            )
            bucket = evidence_by_trait[tid]
            for key in ("evidence_positive", "evidence_negative", "evidence_missing"):
                for item in row.get(key) or []:
                    s = str(item or "").strip()
                    if s and s not in bucket[key]:
                        bucket[key].append(s)

    merged: dict[str, tuple[TraitLevel, float, list[dict]]] = {}
    max_spread = 0.0
    for tid, levels in votes_by_trait.items():
        if not levels:
            continue
        level, spread = merge_trait_level_votes(levels)
        max_spread = max(max_spread, spread)
        merged[tid] = (level, spread, vote_rows_by_trait[tid])
    llm_evidence = {
        tid: dict(evidence_by_trait[tid])
        for tid in evidence_by_trait
        if any(evidence_by_trait[tid].get(k) for k in ("evidence_positive", "evidence_negative", "evidence_missing"))
    }
    return merged, max_spread, llm_evidence
