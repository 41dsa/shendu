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
