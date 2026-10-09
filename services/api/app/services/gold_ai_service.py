"""纯 AI 金标：按题目/标准自动生成高·中·低参考作文与期望分区间。"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from sqlalchemy.orm import Session

from app.models.entities import CredentialRole, GoldSample, Question
from app.services.ai_client import chat_completion_text, get_credential
from app.services.standard_engine.standard_store import get_active_standard_payload

GoldTier = Literal["low", "mid", "high"]
TIERS: tuple[GoldTier, ...] = ("low", "mid", "high")
AUTO_NOTE = "auto:ai_gold"


def _word_bounds(question: Question) -> tuple[int, int]:
    meta = question.material_structured or {}
    wmin = int(meta.get("word_min") or 800)
    wmax = int(meta.get("word_max") or question.word_limit or 1200)
    return wmin, wmax


def expected_score_band(total_score: int, tier: GoldTier) -> tuple[int, int]:
    total = max(total_score, 40)
    if tier == "low":
        return 0, max(8, int(total * 0.32))
    if tier == "mid":
        return int(total * 0.55), int(total * 0.72)
    return int(total * 0.78), min(total, int(total * 0.92))


def gold_sample_id(question_id: str, tier: GoldTier) -> str:
    short = question_id.replace("-", "")[:12]
    return f"ai-gold-{short}-{tier}"


def _stub_paragraph(repeat: str, count: int) -> str:
    return "".join(repeat for _ in range(count))


def generate_reference_essay_stub(question: Question, tier: GoldTier) -> str:
    wmin, wmax = _word_bounds(question)
    theme = (question.prompt or question.title or "申论主题")[:120]
    if tier == "low":
        return f"围绕{theme[:40]}，应当加强工作、落实要求，提高水平。（AI 低分对照 stub，字数不足）"
    if tier == "mid":
        body = (
            f"【自拟标题】立足实际推进相关工作\n\n"
            f"当前，{theme} 已成为重要议题。材料反映的成绩与问题说明，"
            f"既不能简单照搬技术方案，也不能忽视基层执行难度。"
            f"应坚持问题导向，完善制度，强化协同，在法治轨道上推动工作落地。"
            f"同时注重培训与反馈，避免形式主义，让政策真正惠及群众。"
        )
        pad = _stub_paragraph("要统筹规划、精准施策，增强获得感。", max(0, (wmin // 40) - 2))
        return body + "\n\n" + pad
    body = (
        f"【自拟标题】以系统思维回应时代命题\n\n"
        f"面对 {theme[:80]}，需把握战略与战术的统一。"
        f"一方面，以数据与流程再造提升效率，打破信息壁垒；"
        f"另一方面，以责任清单与监督评估保障公平，防止技术异化。"
        f"从材料中的正反案例可见，成功在于持续运营与共建共享，"
        f"而非一次性项目堆砌。政府、市场与社会应各尽其责，"
        f"在法治框架内形成可复制的实践路径。"
        f"\n\n其二，聚焦基层减负，减少无效考核，把精力用在解决群众急难愁盼上。"
        f"其三，完善人才与安全保障，确保数字化建设可持续。"
        f"\n\n总之，只有坚持人民立场、强化制度供给、提升数字素养，"
        f"方能将愿景转化为治理效能，书写高质量发展新篇章。"
    )
    pad = _stub_paragraph("这要求我们以更大决心、更实举措推进改革。", max(0, (wmax // 50) - 4))
    return body + "\n\n" + pad


async def generate_reference_essay_llm(
    db: Session,
    admin_user_id: str,
    question: Question,
    tier: GoldTier,
) -> str:
    cred = get_credential(db, admin_user_id, CredentialRole.primary)
    if not cred:
        raise ValueError("管理员未配置 BYOK")
    std = get_active_standard_payload(db, question.id) or {}
    q_std = std.get("question_standard") or {}
    focus = q_std.get("focus_points") or []
    wmin, wmax = _word_bounds(question)
    tier_hint = {
        "low": "故意写得很差：偏题、空洞、字数明显不足 200 字",
        "mid": "二类文：结构基本完整、论证一般、少量套话",
        "high": "较高分：立意扣题、结构清晰、论证较充分",
    }[tier]
    system = "你是申论大作文写作助手。只输出正文，不要 JSON，不要解释。"
    user = json.dumps(
        {
            "prompt": question.prompt,
            "material_excerpt": (question.material or "")[:1500],
            "focus_points": focus[:8],
            "word_min": wmin,
            "word_max": wmax,
            "quality_tier": tier,
            "instruction": tier_hint,
        },
        ensure_ascii=False,
    )
    text, _ = await chat_completion_text(cred, system, user, temperature=0.8)
    return text.strip()


def upsert_ai_gold_tier(
    db: Session,
    *,
    question: Question,
    tier: GoldTier,
    reference_answer: str,
    total_score: int,
    source: str,
) -> GoldSample:
    smin, smax = expected_score_band(total_score, tier)
    sid = gold_sample_id(question.id, tier)
    title = f"AI金标·{tier}·{question.title[:40]}"
    note = f"{AUTO_NOTE}; source={source}"
    row = db.get(GoldSample, sid)
    if row:
        row.title = title
        row.reference_answer = reference_answer
        row.expected_score_min = smin
        row.expected_score_max = smax
        row.note = note
        row.question_id = question.id
    else:
        row = GoldSample(
            id=sid,
            question_id=question.id,
            title=title,
            reference_answer=reference_answer,
            expected_score_min=smin,
            expected_score_max=smax,
            note=note,
        )
        db.add(row)
    return row


async def seed_ai_gold_for_question(
    db: Session,
    question_id: str,
    *,
    admin_user_id: str | None = None,
    mode: str = "auto",
) -> list[GoldSample]:
    question = db.get(Question, question_id)
    if not question:
        raise ValueError("题目不存在")
    std = get_active_standard_payload(db, question_id)
    rubric = (std or {}).get("rubric_standard") or {}
    total_score = int(rubric.get("total_score") or question.score or 40)

    use_llm = mode == "llm" or (mode == "auto" and admin_user_id and get_credential(db, admin_user_id, CredentialRole.primary))
    out: list[GoldSample] = []
    for tier in TIERS:
        if use_llm and admin_user_id:
            essay = await generate_reference_essay_llm(db, admin_user_id, question, tier)
            source = "llm"
        else:
            essay = generate_reference_essay_stub(question, tier)
            source = "stub"
        out.append(
            upsert_ai_gold_tier(
                db,
                question=question,
                tier=tier,
                reference_answer=essay,
                total_score=total_score,
                source=source,
            )
        )
    db.commit()
    return out


def seed_ai_gold_for_question_sync(
    db: Session,
    question_id: str,
    *,
    admin_user_id: str | None = None,
    mode: str = "auto",
) -> list[GoldSample]:
    return asyncio.run(
        seed_ai_gold_for_question(db, question_id, admin_user_id=admin_user_id, mode=mode)
    )
