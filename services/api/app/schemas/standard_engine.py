"""AI 考试标准引擎 — Pydantic 契约（V0.1-E）。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


SourceLevel = Literal["S", "A", "B", "C"]
EssayForm = Literal["topic", "titled", "material_based", "aphorism", "unknown"]
StandardStatus = Literal["draft", "in_review", "published", "archived"]


class SourceRefSchema(BaseModel):
    document_id: str | None = None
    excerpt: str = ""


class DocumentSchema(BaseModel):
    document_id: str
    title: str = ""
    source: str = "manual_upload"
    source_level: SourceLevel = "B"
    exam: str = ""
    year: int | None = None
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class EssayQuestionSchema(BaseModel):
    question_id: str
    question_no: int | None = None
    question_type: Literal["essay"] = "essay"
    prompt: str
    requirements: str = ""
    word_min: int = 800
    word_max: int = 1200
    score: int = 40
    material_optional: str = ""
    exam: str = ""
    year: int | None = None
    document_refs: list[str] = Field(default_factory=list)


class ThesisScopeSchema(BaseModel):
    must_address: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)


class StructureExpectationSchema(BaseModel):
    paragraphs_min: int = 4
    has_thesis_statement: bool = True
    sub_thesis_count_hint: list[int] = Field(default_factory=lambda: [2, 3])


class QuestionStandardSchema(BaseModel):
    question_id: str
    version: int = 1
    essay_form: EssayForm = "topic"
    proposition_task: str = "论证观点"
    thesis_scope: ThesisScopeSchema = Field(default_factory=ThesisScopeSchema)
    structure_expectation: StructureExpectationSchema = Field(default_factory=StructureExpectationSchema)
    answer_scope: str = "自选角度"
    abilities_focus: list[str] = Field(default_factory=lambda: ["A1", "A2", "A3"])
    keywords: list[str] = Field(default_factory=list)
    focus_points: list[str] = Field(default_factory=list)
    source_refs: list[SourceRefSchema] = Field(default_factory=list)


class MaterialAnalysisSchema(BaseModel):
    question_id: str
    themes: list[str] = Field(default_factory=list)
    facts: list[dict[str, str]] = Field(default_factory=list)
    viewpoints: list[dict[str, str]] = Field(default_factory=list)
    usable_for_argument: list[str] = Field(default_factory=list)
    not_required_to_quote: bool = True


class RubricCriterionSchema(BaseModel):
    id: str
    dimension_id: str
    ability_id: str = "A1"
    core: str
    observable_signals: list[str] = Field(default_factory=list)
    acceptable_expressions: list[str] = Field(default_factory=list)
    typical_gaps: list[str] = Field(default_factory=list)
    counter_examples: list[str] = Field(default_factory=list)
    issue_tags: list[str] = Field(default_factory=list)
    max_score: float = 0
    weight: float = 0
    confidence: float = 0.85
    source_refs: list[SourceRefSchema] = Field(default_factory=list)


class RubricDimensionSchema(BaseModel):
    id: str
    label: str
    max_score: int
    ability: str = "A1"
    required: bool = True
    criteria: list[str] = Field(default_factory=list)


class LossRuleSchema(BaseModel):
    id: str
    when: str
    dimension_id: str
    deduction_cap: float
    issue_tag: str = ""
    explanation_template: str = ""


class RubricStandardSchema(BaseModel):
    question_id: str
    version: int = 1
    total_score: int = 40
    dimensions: list[RubricDimensionSchema] = Field(default_factory=list)
    criteria: list[RubricCriterionSchema] = Field(default_factory=list)
    scoring_rules: dict[str, Any] = Field(default_factory=dict)
    loss_rules: list[LossRuleSchema] = Field(default_factory=list)


class ValidationResultSchema(BaseModel):
    question_id: str
    standard_version: int = 1
    checks: list[dict[str, Any]] = Field(default_factory=list)
    overall_passed: bool = False
    blocking_issues: list[str] = Field(default_factory=list)


class StandardJobCreateRequest(BaseModel):
    question_id: str
    document_ids: list[str] = Field(default_factory=list)


class LinkDocumentsRequest(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class StandardDocumentCreateRequest(BaseModel):
    title: str
    source_level: SourceLevel = "B"
    exam: str = ""
    year: int | None = None
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
