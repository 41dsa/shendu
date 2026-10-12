from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.matching import apply_arbitration_to_hit
from app.domain.scoring_engine.types import PointHit, ScoringPoint
from app.models.entities import CredentialRole, ScoringMatchCache, UserProviderCredential
from app.services.ai_client import AiCallError, chat_completion_json, get_credential


def _cache_key(point: ScoringPoint, paragraph: str) -> str:
    raw = f"{point.point_id}|{point.text}|{paragraph[:500]}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _lookup_cache(db: Session, key: str) -> ScoringMatchCache | None:
    return db.query(ScoringMatchCache).filter(ScoringMatchCache.cache_key == key).first()


def _store_cache(db: Session, key: str, *, accepted: bool, reason: str) -> None:
    row = _lookup_cache(db, key)
    if row:
        row.accepted = accepted
        row.reason = reason[:500]
    else:
        db.add(ScoringMatchCache(cache_key=key, accepted=accepted, reason=reason[:500]))
    db.commit()


async def arbitrate_borderline_hits(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    essay: str,
    hits: list[PointHit],
    points: list[ScoringPoint],
) -> list[PointHit]:
    if not settings.scoring_llm_arbitration_enabled:
        return hits
    cred = get_credential(db, user_id, CredentialRole.primary)
    if not cred:
        return hits

    by_id = {p.point_id: p for p in points}
    updated: list[PointHit] = []
    for hit in hits:
        if hit.status != "borderline":
            updated.append(hit)
            continue
        point = by_id.get(hit.point_id)
        if not point or not hit.evidence:
            updated.append(hit)
            continue
        key = _cache_key(point, hit.evidence)
        cached = _lookup_cache(db, key)
        if cached:
            updated.append(apply_arbitration_to_hit(hit, accepted=cached.accepted, reason=cached.reason))
            continue
        accepted, reason = await _llm_arbitrate(cred, point, hit.evidence)
        _store_cache(db, key, accepted=accepted, reason=reason)
        updated.append(apply_arbitration_to_hit(hit, accepted=accepted, reason=reason))
    return updated


async def _llm_arbitrate(cred: UserProviderCredential, point: ScoringPoint, paragraph: str) -> tuple[bool, str]:
    system = (
        "你是申论语义仲裁员。判断考生段落是否在语义上覆盖采分点。"
        '仅输出 JSON：{"accept": boolean, "reason": string}'
    )
    user = json.dumps(
        {"scoring_point": point.text, "keywords": point.keywords, "user_paragraph": paragraph},
        ensure_ascii=False,
    )
    try:
        raw, _usage = await chat_completion_json(cred, system, user)
        data = json.loads(raw)
        return bool(data.get("accept")), str(data.get("reason") or "")[:400]
    except (AiCallError, json.JSONDecodeError):
        return False, "仲裁调用失败，按未命中处理"
