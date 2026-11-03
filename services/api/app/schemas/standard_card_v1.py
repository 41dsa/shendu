"""PRD §4.2 题目标准卡 V1 完整契约（与 QuestionStandardSchema 并存，可渐进迁移）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.standard_engine import StandardStatus


class KeywordRelationV1(BaseModel):
    a: str
    b: str
    relation: str = "相关"


class ThesisSpaceV1(BaseModel):
    """核心 / 可接受 / 边缘 / 偏题 / 跑题立意空间。"""

    core: list[str] = Field(default_factory=list)
    acceptable: list[str] = Field(default_factory=list)
    edge_acceptable: list[str] = Field(default_factory=list)
    off_topic: list[str] = Field(default_factory=list)
    severe_off_topic: list[str] = Field(default_factory=list)


class MaterialFactV1(BaseModel):
    fact: str
    source_anchor: str = ""


class TraitRubricAdjustmentV1(BaseModel):
    trait_id: str
    weight_override: float | None = None
    interval_span_factor: float | None = None
    level_cap: Literal["L0", "L1", "L2", "L3", "L4"] | None = None


class StandardCardV1Schema(BaseModel):
    question_id: str
    standard_version: int = 1
    review_status: StandardStatus = "draft"
    theme: str = ""
    proposition_task: str = "论证观点"
    keywords: list[str] = Field(default_factory=list)
    keyword_relations: list[KeywordRelationV1] = Field(default_factory=list)
    core_problem: str = ""
    thesis_space: ThesisSpaceV1 = Field(default_factory=ThesisSpaceV1)
    material_facts: list[MaterialFactV1] = Field(default_factory=list)
    material_logic: list[str] = Field(default_factory=list)
    recommended_argument_directions: list[str] = Field(default_factory=list)
    recommended_analysis_dimensions: list[str] = Field(default_factory=list)
    recommended_policy_directions: list[str] = Field(default_factory=list)
    material_sentence_anchors: list[str] = Field(default_factory=list)
    trait_rubric_adjustments: list[TraitRubricAdjustmentV1] = Field(default_factory=list)
    dispute_marks: list[str] = Field(default_factory=list)
    schema_version: Literal["standard_card_v1"] = "standard_card_v1"


def standard_card_v1_from_legacy(question_id: str, raw: dict[str, Any]) -> StandardCardV1Schema:
    """从现网 question_standard JSON + 上下文片段组装 V1 标准卡。"""
    if raw.get("schema_version") == "standard_card_v1":
        data = dict(raw)
        data.setdefault("question_id", question_id)
        return StandardCardV1Schema.model_validate(data)

    thesis = raw.get("thesis_scope") or {}
    if isinstance(thesis, dict):
        must_address = list(thesis.get("must_address") or thesis.get("core") or [])
        must_avoid = list(thesis.get("must_avoid") or [])
    else:
        must_address, must_avoid = [], []

    off = [x for x in must_avoid if "偏题" in str(x)]
    severe = [x for x in must_avoid if "跑题" in str(x)]

    return StandardCardV1Schema(
        question_id=question_id,
        standard_version=int(raw.get("version") or 1),
        review_status=raw.get("review_status") or "draft",
        theme=str(raw.get("theme") or ""),
        proposition_task=str(raw.get("proposition_task") or "论证观点"),
        keywords=list(raw.get("keywords") or raw.get("focus_points") or []),
        keyword_relations=[KeywordRelationV1.model_validate(k) for k in raw.get("keyword_relations") or [] if isinstance(k, dict)],
        core_problem=str(raw.get("core_problem") or ""),
        thesis_space=ThesisSpaceV1(
            core=must_address,
            acceptable=list(raw.get("acceptable_theses") or thesis.get("acceptable") or []),
            edge_acceptable=list(raw.get("edge_acceptable_theses") or []),
            off_topic=list(raw.get("off_topic_directions") or off),
            severe_off_topic=list(raw.get("severe_off_topic_directions") or severe),
        ),
        material_facts=[
            MaterialFactV1.model_validate(f) for f in raw.get("material_facts") or [] if isinstance(f, dict)
        ],
        material_logic=[str(x) for x in raw.get("material_logic") or []],
        recommended_argument_directions=[str(x) for x in raw.get("recommended_argument_directions") or []],
        recommended_analysis_dimensions=[str(x) for x in raw.get("recommended_analysis_dimensions") or []],
        recommended_policy_directions=[str(x) for x in raw.get("recommended_policy_directions") or []],
        material_sentence_anchors=[str(x) for x in raw.get("material_sentence_anchors") or []],
        trait_rubric_adjustments=[
            TraitRubricAdjustmentV1.model_validate(t)
            for t in raw.get("trait_rubric_adjustments") or []
            if isinstance(t, dict)
        ],
        dispute_marks=[str(x) for x in raw.get("dispute_marks") or []],
    )


def is_standard_card_published(card: StandardCardV1Schema) -> bool:
    return card.review_status == "published"
