"""M4/M5：LLM 标准生成（P01～P04、失分规则模板）。"""

import os
from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, label_to_ability
from app.domain.standard_engine.confidence import compute_confidence_score
from app.domain.standard_engine.rubric_agreement import rubric_candidates_agreement
from app.domain.standard_engine.rubric_math import normalize_dimension_scores
from app.models.entities import CredentialRole, PromptPurpose, UserProviderCredential
from app.services.ai_client import get_credential
from app.schemas.standard_engine import (
    EssayQuestionSchema,
    MaterialAnalysisSchema,
    QuestionStandardSchema,
    RubricCriterionSchema,
    RubricStandardSchema,
    LossRuleSchema,
)
from app.services.standard_engine.llm_json import call_standard_llm, validate_model


def _map_essay_form(value: str) -> str:
    allowed = {"topic", "titled", "material_based", "aphorism", "unknown"}
    return value if value in allowed else "topic"


async def generate_question_standard_llm(
    db: Session,
    cred: UserProviderCredential,
    essay: EssayQuestionSchema,
    *,
    user_id: str,
    job_id: str,
) -> QuestionStandardSchema:
    payload = {
        "prompt": essay.prompt,
        "requirements": essay.requirements,
        "material_optional": essay.material_optional[:4000],
        "exam": essay.exam,
        "score": essay.score,
        "word_min": essay.word_min,
        "word_max": essay.word_max,
    }
    data, _raw = await call_standard_llm(
        db,
        cred=cred,
        purpose=PromptPurpose.standard_p01,
        user_payload=payload,
        user_id=user_id,
        job_id=job_id,
        call_type="standard_p01",
    )
    if "essay_form" in data:
        data["essay_form"] = _map_essay_form(str(data.get("essay_form")))
    data["question_id"] = essay.question_id
    if not data.get("focus_points"):
        data["focus_points"] = ["观点是否扣题", "结构是否完整", "论证是否充分"]
    return validate_model(QuestionStandardSchema, data)  # type: ignore[return-value]


async def generate_material_analysis_llm(
    db: Session,
    cred: UserProviderCredential,
    essay: EssayQuestionSchema,
    q_std: QuestionStandardSchema,
    *,
    user_id: str,
    job_id: str,
) -> MaterialAnalysisSchema:
    if not essay.material_optional.strip():
        return MaterialAnalysisSchema(question_id=essay.question_id)
    payload = {
        "material_optional": essay.material_optional[:6000],
        "keywords": q_std.keywords,
    }
    data, _ = await call_standard_llm(
        db,
        cred=cred,
        purpose=PromptPurpose.standard_p02,
        user_payload=payload,
        user_id=user_id,
        job_id=job_id,
        call_type="standard_p02",
    )
    if not data:
        return MaterialAnalysisSchema(question_id=essay.question_id)
    data["question_id"] = essay.question_id
    return validate_model(MaterialAnalysisSchema, data)  # type: ignore[return-value]


async def generate_rubric_llm(
    db: Session,
    cred: UserProviderCredential,
    essay: EssayQuestionSchema,
    q_std: QuestionStandardSchema,
    mat: MaterialAnalysisSchema,
    doc_excerpts: list[str],
    *,
    user_id: str,
    job_id: str,
) -> tuple[dict[str, Any], RubricStandardSchema]:
    skeleton = [
        {"id": d["id"], "label": d["label"], "ability": d.get("ability", "A1")} for d in DEFAULT_RUBRIC_DIMENSIONS
    ]
    p03_payload = {
        "question_standard": q_std.model_dump(),
        "material_analysis": mat.model_dump(),
        "reference_excerpts": doc_excerpts[:5],
        "dimension_skeleton": skeleton,
        "total_score": essay.score,
    }
    cand_data, cand_raw = await call_standard_llm(
        db,
        cred=cred,
        purpose=PromptPurpose.standard_p03,
        user_payload=p03_payload,
        user_id=user_id,
        job_id=job_id,
        call_type="standard_p03",
    )
    candidates = cand_data.get("candidates") or []
    model_agreement = 0.8
    consensus_candidates: list[dict[str, Any]] = []
    if os.environ.get("STANDARD_DUAL_MODEL", "0").lower() in ("1", "true", "yes"):
        cred_consensus = get_credential(db, user_id, CredentialRole.consensus)
        if cred_consensus and cred_consensus.id != cred.id:
            cand2_data, _ = await call_standard_llm(
                db,
                cred=cred_consensus,
                purpose=PromptPurpose.standard_p03,
                user_payload=p03_payload,
                user_id=user_id,
                job_id=job_id,
                call_type="standard_p03_consensus",
            )
            consensus_candidates = cand2_data.get("candidates") or []
            model_agreement = rubric_candidates_agreement(candidates, consensus_candidates)

    p04_payload = {
        "candidates": candidates,
        "total_score": essay.score,
        "dimension_skeleton": skeleton,
    }
    merged_data, merged_raw = await call_standard_llm(
        db,
        cred=cred,
        purpose=PromptPurpose.standard_p04,
        user_payload=p04_payload,
        user_id=user_id,
        job_id=job_id,
        call_type="standard_p04",
    )

    dimensions = normalize_dimension_scores(merged_data.get("dimensions") or [], essay.score)
    criteria_raw = merged_data.get("criteria") or candidates
    criteria: list[RubricCriterionSchema] = []
    for i, c in enumerate(criteria_raw):
        if not c.get("id"):
            c["id"] = f"RC{i+1:03d}"
        if not c.get("confidence"):
            c["confidence"] = compute_confidence_score(
                {
                    "source_trust": 0.85,
                    "prompt_trace": 0.88,
                    "reference_support": 0.82,
                    "model_agreement": model_agreement,
                    "ability_alignment": 1.0,
                }
            )
        if not c.get("ability_id") and c.get("dimension_id"):
            dim = next((d for d in dimensions if d.get("id") == c.get("dimension_id")), None)
            if dim:
                c["ability_id"] = dim.get("ability") or label_to_ability(str(dim.get("label") or ""))
        criteria.append(validate_model(RubricCriterionSchema, c))  # type: ignore[arg-type]

    rubric = RubricStandardSchema(
        question_id=essay.question_id,
        total_score=essay.score,
        dimensions=dimensions,  # type: ignore[arg-type]
        criteria=criteria,
        scoring_rules=merged_data.get("scoring_rules")
        or {"partial_hit_policy": "partial 给 50% 准则分"},
        loss_rules=[],
    )
    debug = {
        "candidates": candidates,
        "candidates_raw_len": len(cand_raw or ""),
        "merged_raw_len": len(merged_raw or ""),
        "model_agreement": model_agreement,
        "consensus_candidates": consensus_candidates,
    }
    return debug, rubric


async def assess_reference_coverage_llm(
    db: Session,
    cred: UserProviderCredential,
    *,
    question_standard: QuestionStandardSchema,
    rubric: RubricStandardSchema,
    reference_excerpts: list[str],
    user_id: str,
    job_id: str,
) -> dict[str, Any]:
    """Prompt P05：参考覆盖语义校验。"""
    payload = {
        "question_standard": question_standard.model_dump(),
        "rubric_standard": rubric.model_dump(),
        "reference_excerpts": reference_excerpts[:20],
    }
    data, raw = await call_standard_llm(
        db,
        cred=cred,
        purpose=PromptPurpose.standard_p05,
        user_payload=payload,
        user_id=user_id,
        job_id=job_id,
        call_type="standard_p05",
    )
    data = dict(data)
    data["raw_len"] = len(raw or "")
    return data


def build_loss_rules(rubric: RubricStandardSchema) -> list[LossRuleSchema]:
    rules: list[LossRuleSchema] = []
    for i, c in enumerate(rubric.criteria):
        tag = (c.issue_tags or ["Q24"])[0]
        rules.append(
            LossRuleSchema(
                id=f"LR{i+1:03d}",
                when=f"gap_{c.id}",
                dimension_id=c.dimension_id,
                deduction_cap=min(float(c.max_score), 8.0),
                issue_tag=tag,
                explanation_template=f"存在「{(c.typical_gaps or ['质量不足'])[0]}」类问题",
            )
        )
    return rules[:12]
