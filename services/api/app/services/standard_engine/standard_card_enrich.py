"""M-03/06/07/08：从 question_std + material_analysis 补全 StandardCardV1 字段。"""

from __future__ import annotations

from typing import Any

from app.schemas.standard_card_v1 import (
    KeywordRelationV1,
    MaterialFactV1,
    StandardCardV1Schema,
    ThesisSpaceV1,
    TraitRubricAdjustmentV1,
    standard_card_v1_from_legacy,
)
from app.schemas.standard_engine import MaterialAnalysisSchema, QuestionStandardSchema


def _as_mat(raw: MaterialAnalysisSchema | dict[str, Any]) -> MaterialAnalysisSchema:
    if isinstance(raw, MaterialAnalysisSchema):
        return raw
    return MaterialAnalysisSchema.model_validate(raw)


def _as_qstd(raw: QuestionStandardSchema | dict[str, Any]) -> QuestionStandardSchema:
    if isinstance(raw, QuestionStandardSchema):
        return raw
    return QuestionStandardSchema.model_validate(raw)


def enrich_standard_card_v1(
    card: StandardCardV1Schema,
    *,
    q_std: QuestionStandardSchema | dict[str, Any],
    mat: MaterialAnalysisSchema | dict[str, Any],
    rubric: dict[str, Any] | None = None,
) -> StandardCardV1Schema:
    q = _as_qstd(q_std)
    m = _as_mat(mat)
    updates: dict[str, Any] = {}

    ts = card.thesis_space
    if not ts.core and (q.thesis_scope.must_address or q.thesis_scope.must_avoid):
        avoid = [str(x) for x in q.thesis_scope.must_avoid or []]
        off = [x for x in avoid if "偏题" in x]
        severe = [x for x in avoid if "跑题" in x]
        generic_avoid = [x for x in avoid if x not in off and x not in severe]
        if not off and generic_avoid:
            off = generic_avoid[:4]
        updates["thesis_space"] = ThesisSpaceV1(
            core=[str(x) for x in q.thesis_scope.must_address or []],
            acceptable=list(ts.acceptable),
            edge_acceptable=list(ts.edge_acceptable),
            off_topic=off or list(ts.off_topic),
            severe_off_topic=severe or list(ts.severe_off_topic),
        )

    if not card.core_problem.strip():
        theme = card.theme or (m.themes[0] if m.themes else "")
        kw = card.keywords or q.keywords
        focus = "、".join(kw[:3]) if kw else "题干核心"
        updates["core_problem"] = f"围绕「{theme or focus}」展开论证，回应{q.proposition_task or '题目任务'}。"

    if not card.material_facts and (m.facts or m.themes):
        facts: list[MaterialFactV1] = []
        for row in m.facts or []:
            if isinstance(row, dict) and row.get("fact"):
                facts.append(MaterialFactV1(fact=str(row["fact"]), source_anchor=str(row.get("source") or "")))
        if not facts and m.themes:
            for t in m.themes[:6]:
                facts.append(MaterialFactV1(fact=str(t), source_anchor="material_theme"))
        updates["material_facts"] = facts

    if not card.material_logic:
        logic: list[str] = []
        for vp in m.viewpoints or []:
            if isinstance(vp, dict):
                logic.append(f"{vp.get('viewpoint', '')} → {vp.get('implication', '')}".strip(" →"))
        if not logic and m.usable_for_argument:
            logic = [f"材料可用于论证：{x}" for x in m.usable_for_argument[:5]]
        updates["material_logic"] = [x for x in logic if x.strip()][:8]

    if not card.recommended_argument_directions:
        args = list(m.usable_for_argument or m.themes or [])[:4]
        updates["recommended_argument_directions"] = [f"从「{a}」切入论证" for a in args if a]

    if not card.recommended_analysis_dimensions:
        updates["recommended_analysis_dimensions"] = [
            "原因与机制",
            "影响与风险",
            "辩证关系",
        ][: max(1, len(m.themes))]

    if not card.recommended_policy_directions:
        updates["recommended_policy_directions"] = [
            "完善制度与机制",
            "强化基层执行与协同",
            "科技赋能与数据治理",
        ][:2]

    if not card.keyword_relations and len(card.keywords) >= 2:
        rels: list[KeywordRelationV1] = []
        base = card.keywords[0]
        for other in card.keywords[1:4]:
            rels.append(KeywordRelationV1(a=base, b=other, relation="相关"))
        updates["keyword_relations"] = rels

    if not card.trait_rubric_adjustments and rubric:
        adjs: list[TraitRubricAdjustmentV1] = []
        for crit in rubric.get("criteria") or []:
            if not isinstance(crit, dict):
                continue
            dim = str(crit.get("dimension_id") or "")
            tid_map = {"D01": "T1", "D02": "T3", "D03": "T4", "D04": "T8"}
            tid = tid_map.get(dim, "")
            if not tid:
                continue
            conf = float(crit.get("confidence") or 0.85)
            if conf < 0.75:
                adjs.append(TraitRubricAdjustmentV1(trait_id=tid, interval_span_factor=1.15))
        if adjs:
            updates["trait_rubric_adjustments"] = adjs

    if not card.material_sentence_anchors and m.themes:
        updates["material_sentence_anchors"] = [str(t) for t in m.themes[:8]]

    if not updates:
        return card
    return card.model_copy(update=updates)


def enrich_card_payload_from_job_context(
    question_id: str,
    consensus_payload: dict[str, Any],
    *,
    q_std: QuestionStandardSchema | dict[str, Any],
    mat: MaterialAnalysisSchema | dict[str, Any],
    rubric: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_card = dict(consensus_payload.get("standard_card_v1") or {})
    card = standard_card_v1_from_legacy(question_id, raw_card) if raw_card else standard_card_v1_from_legacy(
        question_id, _as_qstd(q_std).model_dump()
    )
    enriched = enrich_standard_card_v1(card, q_std=q_std, mat=mat, rubric=rubric)
    out = dict(consensus_payload)
    out["standard_card_v1"] = enriched.model_dump()
    out["material_enriched"] = True
    return out
