"""PRD ② 题目标准卡：从批改上下文组装单题结构化标准。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from typing import TYPE_CHECKING

from app.schemas.standard_card_v1 import StandardCardV1Schema, is_standard_card_published, standard_card_v1_from_legacy

if TYPE_CHECKING:
    from app.domain.essay_grading_context import EssayGradingContext


@dataclass
class QuestionStandardCard:
    question_id: str
    version: int | None
    review_status: str
    reviewed: bool
    theme: str
    task: str
    keywords: list[str]
    keyword_relations: list[dict[str, str]]
    core_problem: str
    core_theses: list[str]
    acceptable_theses: list[str]
    edge_theses: list[str]
    off_topic_hints: list[str]
    severe_off_topic_hints: list[str]
    material_anchor_phrases: list[str]
    material_facts: list[dict[str, str]]
    material_logic: list[str]
    recommended_argument: list[str]
    recommended_analysis: list[str]
    recommended_policy: list[str]
    trait_rubric_adjustments: list[dict[str, Any]]
    dispute_marks: list[str] = field(default_factory=list)
    match_confidence: float = 0.85
    v1: StandardCardV1Schema | None = None


def _tokens_from_text(text: str, limit: int = 12) -> list[str]:
    if not text:
        return []
    parts = re.findall(r"[\u4e00-\u9fff]{2,8}", text)
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def build_question_standard_card(ctx: "EssayGradingContext") -> QuestionStandardCard:
    raw_std = dict(getattr(ctx, "question_standard", None) or {})
    qid = ctx.question_id or ctx.cache_context_key

    review_status = str(
        getattr(ctx, "standard_review_status", None)
        or raw_std.get("review_status")
        or ("published" if ctx.standard_version is not None else "draft")
    )
    raw_std["review_status"] = review_status
    if ctx.standard_version is not None:
        raw_std.setdefault("version", ctx.standard_version)

    v1 = standard_card_v1_from_legacy(qid, raw_std)
    if not v1.theme:
        v1 = v1.model_copy(update={"theme": ctx.title or ""})

    keywords = list(v1.keywords)
    for crit in ctx.rubric_criteria or []:
        if not isinstance(crit, dict):
            continue
        core = str(crit.get("core") or "").strip()
        if core:
            keywords.append(core)
        for expr in crit.get("acceptable_expressions") or []:
            if expr:
                keywords.append(str(expr))
    keywords = [k for k in dict.fromkeys(keywords) if k][:32]

    off_topic = list(v1.thesis_space.off_topic)
    severe = list(v1.thesis_space.severe_off_topic)
    for rule in ctx.loss_rules or []:
        if not isinstance(rule, dict):
            continue
        label = str(rule.get("label") or rule.get("reason") or rule.get("when") or "")
        if "跑题" in label or rule.get("severity") == "severe":
            severe.append(label or str(rule.get("pattern") or ""))
        elif "偏题" in label:
            off_topic.append(label)

    anchors = list(v1.material_sentence_anchors)
    if not anchors:
        anchors = _tokens_from_text(ctx.reference_material or "", limit=16)
    for mf in v1.material_facts:
        if mf.source_anchor:
            anchors.append(mf.source_anchor)

    published = is_standard_card_published(v1)
    match_conf = 0.92 if published else 0.55 if review_status == "draft" else 0.65

    return QuestionStandardCard(
        question_id=qid,
        version=int(v1.standard_version) if v1.standard_version else None,
        review_status=review_status,
        reviewed=published,
        theme=v1.theme or ctx.title or "",
        task=v1.proposition_task,
        keywords=keywords,
        keyword_relations=[kr.model_dump() for kr in v1.keyword_relations],
        core_problem=v1.core_problem,
        core_theses=list(v1.thesis_space.core),
        acceptable_theses=list(v1.thesis_space.acceptable),
        edge_theses=list(v1.thesis_space.edge_acceptable),
        off_topic_hints=[x for x in off_topic if x],
        severe_off_topic_hints=[x for x in severe if x],
        material_anchor_phrases=anchors[:24],
        material_facts=[mf.model_dump() for mf in v1.material_facts],
        material_logic=list(v1.material_logic),
        recommended_argument=list(v1.recommended_argument_directions),
        recommended_analysis=list(v1.recommended_analysis_dimensions),
        recommended_policy=list(v1.recommended_policy_directions),
        trait_rubric_adjustments=[t.model_dump() for t in v1.trait_rubric_adjustments],
        dispute_marks=list(v1.dispute_marks),
        match_confidence=match_conf,
        v1=v1,
    )
