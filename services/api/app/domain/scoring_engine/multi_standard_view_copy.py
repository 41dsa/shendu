"""R-05：C 档 / 多标准视图文案模板（配置驱动）。"""

from __future__ import annotations

from app.domain.scoring_engine.rubric_loader import load_trait_rubric_document, trait_level_descriptor
from app.domain.scoring_engine.trait_definitions import LEVEL_ORDER, TraitLevel


def _shift_level(level: TraitLevel | str, delta: int) -> str:
    lv = str(level or "L2")
    if lv not in LEVEL_ORDER:
        lv = "L2"
    idx = LEVEL_ORDER.index(lv)  # type: ignore[arg-type]
    return LEVEL_ORDER[max(0, min(len(LEVEL_ORDER) - 1, idx + delta))]


def view_templates() -> dict:
    doc = load_trait_rubric_document()
    raw = doc.get("view_templates") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def format_c_trait_dispute(*, trait_id: str, trait_name: str, level: TraitLevel | str) -> str:
    tpl = str(
        view_templates().get("c_trait_dual_view")
        or "严格视角约 {strict_level}，宽松视角约 {loose_level}：{trait_name}存在标准依赖，不参与得分合成。"
    )
    strict = _shift_level(level, -1)
    loose = _shift_level(level, 1)
    hint = trait_level_descriptor(trait_id, str(level))
    return tpl.format(
        strict_level=strict,
        loose_level=loose,
        trait_id=trait_id,
        trait_name=trait_name,
        level=level,
        level_hint=hint,
    )


def score_view_labels() -> dict[str, str]:
    tpl = view_templates()
    return {
        "strict": str(tpl.get("strict_score_label") or "严格标准（区间偏下限）"),
        "loose": str(tpl.get("loose_score_label") or "宽松标准（区间偏上限）"),
        "baseline": str(tpl.get("baseline_score_label") or "综合标准（加权）"),
        "dependency": str(tpl.get("dependency_section_label") or "标准依赖型维度（不参与得分合成）"),
    }
