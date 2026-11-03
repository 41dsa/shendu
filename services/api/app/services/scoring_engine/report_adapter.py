from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.types import PointHit, ScoringPoint, ScoringTier
from app.domain.essay import label_to_ability


def dimension_rows_from_engine(
    dimension_scores: dict[str, dict[str, float]],
    scoring_dimensions: list[Any],
) -> list[dict[str, Any]]:
    rubric_by_id = {str(d.get("id")): d for d in (scoring_dimensions or []) if isinstance(d, dict)}
    rows: list[dict[str, Any]] = []
    for did, row in dimension_scores.items():
        ref = rubric_by_id.get(did) or {}
        label = str(ref.get("label") or did)
        earned = float(row.get("score") or 0)
        mx = float(row.get("max") or ref.get("max_score") or 10)
        ratio = earned / mx if mx else 0
        hit = "full" if ratio >= 0.85 else "partial" if ratio >= 0.5 else "miss"
        rows.append(
            {
                "id": did,
                "label": label,
                "earned": earned,
                "max": mx,
                "hit": hit,
                "reason": "确定性引擎按采分点覆盖率聚合",
                "evidence_ref": None,
                "ability": ref.get("ability") or label_to_ability(label),
            }
        )
    if not rows and scoring_dimensions:
        for dim in scoring_dimensions:
            if not isinstance(dim, dict):
                continue
            did = str(dim.get("id") or "")
            mx = float(dim.get("max_score") or 10)
            rows.append(
                {
                    "id": did,
                    "label": str(dim.get("label") or did),
                    "earned": 0.0,
                    "max": mx,
                    "hit": "miss",
                    "reason": "",
                    "ability": dim.get("ability") or label_to_ability(str(dim.get("label") or "")),
                }
            )
    return rows


def _point_label(point_id: str, points: list[ScoringPoint] | None) -> str:
    if not points:
        return point_id
    for p in points:
        if p.point_id == point_id:
            text = (p.text or "").strip()
            if not text:
                return point_id
            return text if len(text) <= 48 else text[:45] + "…"
    return point_id


def evidence_chain_from_hits(
    hits: list[PointHit],
    *,
    points: list[ScoringPoint] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen_quotes: set[str] = set()
    for h in hits:
        if h.status not in ("hit", "borderline", "partial", "advisory"):
            continue
        if not h.evidence and h.status != "advisory":
            continue
        quote_key = (h.evidence or "")[:120]
        if quote_key and quote_key in seen_quotes:
            continue
        if quote_key:
            seen_quotes.add(quote_key)
        mx = float(h.max_score or 0)
        earned = float(h.earned or 0)
        if mx > 0:
            earned = round(min(earned, mx), 2)
        chain.append(
            {
                "criterion_id": h.point_id,
                "label": _point_label(h.point_id, points),
                "hit": "full" if h.status == "hit" else "partial" if h.status in ("borderline", "partial") else "miss",
                "user_quote": h.evidence,
                "material_ref": f"作文第{h.evidence_para}段" if h.evidence_para else "",
                "earned": earned,
                "max": mx,
                "reason": h.reason,
            }
        )
        if len(chain) >= limit:
            break
    return chain


def evidence_chain_from_hit_dicts(
    hits: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """旧报告修复：从 payload.scoring_engine.point_hits 重建证据链。"""
    chain: list[dict[str, Any]] = []
    seen_quotes: set[str] = set()
    for h in hits:
        status = str(h.get("status") or "")
        if status not in ("hit", "borderline", "partial", "advisory"):
            continue
        evidence = str(h.get("evidence") or "")
        if not evidence and status != "advisory":
            continue
        quote_key = evidence[:120]
        if quote_key and quote_key in seen_quotes:
            continue
        if quote_key:
            seen_quotes.add(quote_key)
        mx = float(h.get("max_score") or 0)
        earned = float(h.get("earned") or 0)
        if mx > 0:
            earned = round(min(earned, mx), 2)
        pid = str(h.get("point_id") or "")
        label = str(h.get("label") or h.get("point_text") or pid).strip()
        dim_id = str(h.get("dimension_id") or "")
        if len(label) > 48:
            label = label[:45] + "…"
        chain.append(
            {
                "criterion_id": pid,
                "label": label or pid,
                "hit": "full" if status == "hit" else "partial" if status in ("borderline", "partial") else "miss",
                "user_quote": evidence,
                "material_ref": f"作文第{h.get('evidence_para')}段" if h.get("evidence_para") else "",
                "earned": earned,
                "max": mx,
                "reason": str(h.get("reason") or ""),
            }
        )
        if len(chain) >= limit:
            break
    return chain


def point_hits_payload(hits: list[PointHit], points: list[ScoringPoint] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    by_id = {p.point_id: p for p in (points or [])}
    for h in hits:
        pt = by_id.get(h.point_id)
        mx = float(h.max_score or 0)
        earned = float(h.earned or 0)
        if mx > 0:
            earned = round(min(earned, mx), 2)
        out.append(
            {
                "point_id": h.point_id,
                "dimension_id": (pt.dimension_id if pt else "") or "",
                "label": _point_label(h.point_id, points),
                "point_text": (pt.text if pt else "") or "",
                "status": h.status,
                "match_stage": h.match_stage,
                "evidence": h.evidence,
                "evidence_para": h.evidence_para,
                "weight": h.weight,
                "earned": earned,
                "max_score": mx,
                "reason": h.reason,
                "suggestion": h.suggestion,
            }
        )
    return out


def tier_summary(tier: ScoringTier) -> str:
    return f"{tier.label}（{tier.reason}）"


_LEVEL_TO_RATIO = {"L4": 0.92, "L3": 0.78, "L2": 0.58, "L1": 0.38, "L0": 0.12}


def trait_rows_as_scoring_points(
    trait_payload: list[dict[str, Any]],
    *,
    max_score: float,
) -> list[dict[str, Any]]:
    """兼容报告 API：以 Trait 诊断填充 scoring_points 形态。"""
    per = max_score / max(len(trait_payload), 1)
    rows: list[dict[str, Any]] = []
    for t in trait_payload:
        level = str(t.get("level") or "L2")
        ratio = _LEVEL_TO_RATIO.get(level, 0.5)
        earned = round(per * ratio, 2) if t.get("participates_in_score") else 0.0
        mx = round(per, 2) if t.get("participates_in_score") else 0.0
        hit = "full" if ratio >= 0.85 else "partial" if ratio >= 0.5 else "miss"
        if not t.get("participates_in_score"):
            hit = "miss"
        rows.append(
            {
                "id": t.get("trait_id"),
                "label": t.get("name"),
                "earned": earned,
                "max": mx,
                "hit": hit,
                "reason": t.get("conclusion") or "",
                "trait_level": level,
                "evidence_ref": (t.get("evidence_positive") or [None])[0],
                "participates_in_score": t.get("participates_in_score"),
            }
        )
    return rows


def evidence_chain_from_traits(trait_payload: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    for t in trait_payload:
        pos = t.get("evidence_positive") or []
        if not pos:
            continue
        quote = str(pos[0])
        chain.append(
            {
                "criterion_id": t.get("trait_id"),
                "label": t.get("name"),
                "hit": "partial",
                "user_quote": quote,
                "material_ref": "",
                "earned": 0,
                "max": 0,
                "reason": t.get("conclusion") or "",
            }
        )
        if len(chain) >= limit:
            break
    return chain


def tier_from_ability(ability_level: str, max_score: float) -> ScoringTier:
    from app.domain.scoring_engine.level_config import _base_tiers

    tiers = _base_tiers(max_score)
    mapping = {"强": 0, "较强": 1, "一般": 2, "较弱": 3, "严重缺失": 4}
    idx = mapping.get(ability_level, 2)
    idx = min(idx, len(tiers) - 1)
    rule = tiers[idx]
    return ScoringTier(
        tier_id=str(rule["tier_id"]),
        label=str(rule["label"]),
        score_min=float(rule["score_min"]),
        score_max=float(rule["score_max"]),
        reason=f"Trait 引擎能力等级：{ability_level}",
    )
