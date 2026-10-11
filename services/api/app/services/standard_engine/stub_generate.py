"""确定性占位生成（无 LLM），用于打通 pipeline；STD-301 起可替换为 LLM 实现。"""

import re
from typing import Any

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, label_to_ability
from app.domain.standard_engine.confidence import compute_confidence_score
from app.domain.standard_engine.criterion_confidence import enrich_rubric_contract
from app.schemas.standard_engine import (
    EssayQuestionSchema,
    MaterialAnalysisSchema,
    QuestionStandardSchema,
    RubricCriterionSchema,
    RubricDimensionSchema,
    RubricStandardSchema,
)


def question_to_essay_schema(question: Any) -> EssayQuestionSchema:
    meta = question.material_structured or {}
    prompt = (question.prompt or "").strip()
    return EssayQuestionSchema(
        question_id=question.id,
        prompt=prompt,
        requirements=prompt,
        word_min=int(meta.get("word_min") or 800),
        word_max=int(meta.get("word_max") or question.word_limit or 1200),
        score=int(question.score or 40),
        material_optional=(question.material or "") or "",
        exam=str(meta.get("exam") or ""),
    )


def stub_question_standard(essay: EssayQuestionSchema) -> QuestionStandardSchema:
    keywords = re.findall(r"[\u4e00-\u9fff]{2,6}", essay.prompt)[:8]
    form: Any = "material_based" if essay.material_optional.strip() else "topic"
    return QuestionStandardSchema(
        question_id=essay.question_id,
        essay_form=form,
        proposition_task="论证观点",
        thesis_scope={"must_address": keywords[:3], "must_avoid": ["脱离题干空泛议论"]},
        keywords=keywords,
        focus_points=["观点是否扣题", "结构是否完整", "论证是否有论据与分析"],
        abilities_focus=["A1", "A2", "A3"],
    )


def stub_material_analysis(essay: EssayQuestionSchema) -> MaterialAnalysisSchema:
    if not essay.material_optional.strip():
        return MaterialAnalysisSchema(question_id=essay.question_id)
    themes = re.findall(r"[\u4e00-\u9fff]{2,8}", essay.material_optional)[:5]
    return MaterialAnalysisSchema(
        question_id=essay.question_id,
        themes=themes,
        usable_for_argument=themes[:3],
    )


def stub_rubric_standard(essay: EssayQuestionSchema, q_std: QuestionStandardSchema) -> RubricStandardSchema:
    dimensions: list[RubricDimensionSchema] = []
    criteria: list[RubricCriterionSchema] = []
    rubric_dims = DEFAULT_RUBRIC_DIMENSIONS
    per_dim = int(essay.score / max(len(rubric_dims), 1))
    remainder = essay.score - per_dim * len(rubric_dims)
    for i, d in enumerate(rubric_dims):
        max_s = per_dim + (remainder if i == 0 else 0)
        dim_id = str(d.get("id") or f"D0{i+1}")
        label = str(d.get("label") or "")
        cid = f"RC-{dim_id}-001"
        dimensions.append(
            RubricDimensionSchema(
                id=dim_id,
                label=label,
                max_score=max_s,
                ability=str(d.get("ability") or label_to_ability(label)),
                required=bool(d.get("required", True)),
                criteria=[cid],
            )
        )
        components = {
            "source_trust": 0.85,
            "prompt_trace": 0.9,
            "reference_support": 0.8,
            "model_agreement": 0.85,
            "ability_alignment": 1.0,
        }
        criteria.append(
            RubricCriterionSchema(
                id=cid,
                dimension_id=dim_id,
                ability_id=str(d.get("ability") or label_to_ability(label)),
                core=f"{label}：观点清晰、符合题干要求",
                observable_signals=[f"篇章体现{label}相关要求"],
                typical_gaps=[f"{label}薄弱或缺失"],
                issue_tags=["Q21"] if "立意" in label else ["Q24"],
                max_score=float(max_s),
                weight=1.0,
                confidence=compute_confidence_score(components),
            )
        )
    raw = RubricStandardSchema(
        question_id=essay.question_id,
        total_score=essay.score,
        dimensions=dimensions,
        criteria=criteria,
        scoring_rules={
            "partial_hit_policy": "partial 给 50% 准则分",
            "score_confidence_declaration": "medium",
        },
        loss_rules=[],
    )
    enriched = enrich_rubric_contract(raw.model_dump())
    return RubricStandardSchema.model_validate(enriched)
