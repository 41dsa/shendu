"""PRD §4.3 M-11～M-12：三模型标准卡共识合并（高共识入库，分歧写 dispute_marks）。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import CredentialRole
from app.schemas.standard_card_v1 import StandardCardV1Schema, standard_card_v1_from_legacy
from app.schemas.standard_engine import EssayQuestionSchema, QuestionStandardSchema
from app.services.ai_client import get_credential
from app.services.standard_engine.llm_generate import generate_question_standard_llm


@dataclass
class StandardConsensusMeta:
    consensus_score: float
    model_count: int
    model_labels: list[str] = field(default_factory=list)
    dispute_marks: list[str] = field(default_factory=list)
    field_agreement: dict[str, float] = field(default_factory=dict)


def _vote_strings(values: list[str], *, min_votes: int) -> tuple[list[str], list[str]]:
    counter: Counter[str] = Counter(v.strip() for v in values if v and str(v).strip())
    if not counter:
        return [], []
    kept = [k for k, c in counter.items() if c >= min_votes]
    disputed = [k for k, c in counter.items() if c < min_votes]
    return kept, disputed


def merge_standard_cards_v1(cards: list[StandardCardV1Schema]) -> tuple[StandardCardV1Schema, StandardConsensusMeta]:
    if not cards:
        raise ValueError("cards required")
    n = len(cards)
    min_votes = max(2, (2 * n + 2) // 3) if n >= 3 else max(1, n)

    base = cards[0].model_copy(deep=True)
    all_kw: list[str] = []
    themes: list[str] = []
    tasks: list[str] = []
    core_theses: list[str] = []
    for c in cards:
        all_kw.extend(c.keywords)
        themes.append(c.theme)
        tasks.append(c.proposition_task)
        core_theses.extend(c.thesis_space.core)

    kw_kept, kw_disputed = _vote_strings(all_kw, min_votes=min_votes)
    theme_kept, theme_disputed = _vote_strings(themes, min_votes=min_votes)
    task_kept, _ = _vote_strings(tasks, min_votes=min_votes)
    core_kept, core_disputed = _vote_strings(core_theses, min_votes=min_votes)

    disputes: list[str] = []
    if kw_disputed:
        disputes.append("关键词标准依赖：" + "、".join(kw_disputed[:5]))
    if theme_disputed:
        disputes.append("主题表述分歧：" + "、".join(theme_disputed[:3]))
    if core_disputed:
        disputes.append("核心立意分歧：" + "、".join(core_disputed[:3]))

    base.keywords = kw_kept or base.keywords
    if theme_kept:
        base.theme = theme_kept[0]
    if task_kept:
        base.proposition_task = task_kept[0]
    if core_kept:
        base.thesis_space.core = core_kept[:8]

    agree_kw = len(kw_kept) / max(len(set(all_kw)), 1)
    agree_theme = 1.0 if theme_kept else 0.5
    agree_core = len(core_kept) / max(len(set(core_theses)), 1) if core_theses else 1.0
    consensus_score = round((agree_kw + agree_theme + agree_core) / 3.0, 3)

    base.dispute_marks = list(dict.fromkeys(list(base.dispute_marks) + disputes))
    if consensus_score >= 0.85 and not disputes:
        base.review_status = "published"
    else:
        base.review_status = "draft"
        if not disputes:
            base.dispute_marks.append("三模型共识未达发布阈值，仅诊断可用")

    meta = StandardConsensusMeta(
        consensus_score=consensus_score,
        model_count=n,
        dispute_marks=list(base.dispute_marks),
        field_agreement={
            "keywords": round(agree_kw, 3),
            "theme": round(agree_theme, 3),
            "thesis_core": round(agree_core, 3),
        },
    )
    return base, meta


def card_from_question_standard(question_id: str, q_std: QuestionStandardSchema | dict[str, Any]) -> StandardCardV1Schema:
    raw = q_std.model_dump() if isinstance(q_std, QuestionStandardSchema) else dict(q_std)
    ts = raw.get("thesis_scope") or {}
    if isinstance(ts, dict):
        raw.setdefault("acceptable_theses", ts.get("acceptable") or [])
        raw.setdefault("off_topic_directions", ts.get("off_topic") or [])
    return standard_card_v1_from_legacy(question_id, raw)


def apply_card_to_question_standard(q_std: QuestionStandardSchema, card: StandardCardV1Schema) -> QuestionStandardSchema:
    data = q_std.model_dump()
    data["keywords"] = list(card.keywords)
    data["proposition_task"] = card.proposition_task
    data["thesis_scope"] = {
        "must_address": list(card.thesis_space.core),
        "must_avoid": list(card.thesis_space.off_topic) + list(card.thesis_space.severe_off_topic),
    }
    return QuestionStandardSchema.model_validate(data)


async def collect_three_question_standards(
    db: Session,
    *,
    essay: EssayQuestionSchema,
    user_id: str,
    job_id: str,
) -> list[tuple[str, QuestionStandardSchema]]:
    labels: list[tuple[CredentialRole, str]] = [
        (CredentialRole.primary, "primary"),
        (CredentialRole.consensus, "consensus"),
        (CredentialRole.reviewer, "reviewer"),
    ]
    seen: set[int] = set()
    out: list[tuple[str, QuestionStandardSchema]] = []
    for role, label in labels:
        cred = get_credential(db, user_id, role)
        if not cred or cred.id in seen:
            continue
        seen.add(cred.id)
        q = await generate_question_standard_llm(db, cred, essay, user_id=user_id, job_id=job_id)
        out.append((label, q))
    if len(out) < 3 and out:
        base_cred = get_credential(db, user_id, CredentialRole.primary)
        while len(out) < 3 and base_cred:
            out.append((f"primary_repeat_{len(out)}", out[0][1]))
    return out


async def run_standard_consensus_pipeline(
    db: Session,
    *,
    essay: EssayQuestionSchema,
    user_id: str,
    job_id: str,
) -> tuple[QuestionStandardSchema, StandardCardV1Schema, StandardConsensusMeta]:
    drafts = await collect_three_question_standards(db, essay=essay, user_id=user_id, job_id=job_id)
    if not drafts:
        raise ValueError("no credentials for standard consensus")
    cards = [card_from_question_standard(essay.question_id, q) for _, q in drafts]
    merged, meta = merge_standard_cards_v1(cards)
    meta.model_labels = [label for label, _ in drafts]
    q_merged = apply_card_to_question_standard(drafts[0][1], merged)
    return q_merged, merged, meta
