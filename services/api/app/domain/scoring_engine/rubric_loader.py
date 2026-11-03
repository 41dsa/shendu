"""加载 PRD §5 Rubric 配置（JSON）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_API_ROOT = Path(__file__).resolve().parents[3]
_RUBRIC_PATH = _API_ROOT / "data" / "rubric" / "trait_rubric_v1.json"


@lru_cache(maxsize=1)
def load_trait_rubric_document() -> dict[str, Any]:
    with _RUBRIC_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def rubric_version() -> str:
    return str(load_trait_rubric_document().get("rubric_version") or "essay-trait-v1.0.0")


def trait_level_descriptor(trait_id: str, level: str) -> str:
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    row = traits.get(trait_id) or {}
    levels = row.get("levels") or {}
    return str(levels.get(level) or "")


def default_scorable_weights() -> dict[str, float]:
    doc = load_trait_rubric_document()
    raw = doc.get("default_scorable_weights") or {}
    return {str(k): float(v) for k, v in raw.items()}


def ability_by_level() -> dict[str, str]:
    doc = load_trait_rubric_document()
    raw = doc.get("ability_by_level") or {}
    return {str(k): str(v) for k, v in raw.items()}


def trait_catalog_row(trait_id: str) -> dict[str, Any]:
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    row = traits.get(trait_id)
    if not isinstance(row, dict):
        return {}
    return row


def merged_scorable_weights(adjustments: list[dict[str, Any]] | None) -> dict[str, float]:
    weights = dict(default_scorable_weights())
    if not adjustments:
        return weights
    total_override = 0.0
    for adj in adjustments:
        if not isinstance(adj, dict):
            continue
        tid = str(adj.get("trait_id") or "")
        w = adj.get("weight_override")
        if tid and w is not None:
            weights[tid] = float(w)
            total_override += float(w)
    if total_override > 0:
        scale = 1.0 / total_override
        for k in list(weights.keys()):
            if k in {str(a.get("trait_id")) for a in adjustments if isinstance(a, dict)}:
                weights[k] *= scale
    return weights


def trait_score_adjustments(trait_id: str) -> dict[str, list[str]]:
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    row = traits.get(trait_id) or {}
    plus = list(row.get("plus_conditions") or [])
    minus = list(row.get("minus_conditions") or [])
    return {"plus_conditions": plus, "minus_conditions": minus}


def assert_rubric_complete() -> None:
    doc = load_trait_rubric_document()
    traits = doc.get("traits") or {}
    for i in range(1, 9):
        tid = f"T{i}"
        assert tid in traits, f"missing trait {tid}"
        levels = traits[tid].get("levels") or {}
        for lv in ("L0", "L1", "L2", "L3", "L4"):
            assert lv in levels and levels[lv], f"missing {tid}.{lv}"
        plus = traits[tid].get("plus_conditions") or []
        minus = traits[tid].get("minus_conditions") or []
        assert len(plus) >= 1, f"missing {tid}.plus_conditions"
        assert len(minus) >= 1, f"missing {tid}.minus_conditions"
        name = str(traits[tid].get("name") or "").strip()
        assert name, f"missing {tid}.name"
        tier = str(traits[tid].get("standard_tier") or "")
        assert tier in ("A", "B", "C"), f"invalid {tid}.standard_tier"
        assert "participates_in_score" in traits[tid], f"missing {tid}.participates_in_score"
    ab = doc.get("ability_by_level") or {}
    for lv in ("L0", "L1", "L2", "L3", "L4"):
        assert lv in ab and ab[lv], f"missing ability_by_level.{lv}"
