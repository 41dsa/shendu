"""用户自备批改：传统四档阅卷 Prompt（与 PRD Trait V1 路径可配置切换）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.essay_grading_context import EssayGradingContext
from app.models.entities import Submission

_PROMPT_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "prompts" / "custom_traditional_grading.txt"
)


def load_default_custom_traditional_prompt() -> str:
    if _PROMPT_FILE.is_file():
        return _PROMPT_FILE.read_text(encoding="utf-8")
    return "你是一名申论大作文阅卷专家。只输出 JSON。"


def fill_traditional_grading_prompt(
    template: str,
    *,
    ctx: EssayGradingContext,
    essay: str,
    word_min: int,
    word_max: int,
    essay_char_count: int,
    submission: Submission | None = None,
) -> str:
    material = (ctx.reference_material or "").strip()
    prompt_text = (ctx.prompt or "").strip()
    handwriting = ""
    if submission is not None:
        handwriting = str(getattr(submission, "handwriting_note", None) or "").strip()
    if not handwriting:
        handwriting = "（未提供，文本批改默认不据卷面扣分，需人工复核）"
    replacements = {
        "{{题目}}": prompt_text.split("\n")[0][:200] if prompt_text else "（见作答要求）",
        "{{材料}}": material if material else "（未提供）",
        "{{作答要求}}": prompt_text or "（未提供）",
        "{{规定字数}}": f"{word_min}～{word_max} 字（约 {essay_char_count} 字）",
        "{{作文正文}}": essay,
        "{{卷面情况}}": handwriting,
        "{{是否提供材料}}": "是" if material else "否",
        "{{满分}}": str(int(ctx.score or 40)),
    }
    out = template
    for key, val in replacements.items():
        out = out.replace(key, val)
    return out


def normalize_traditional_marking_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """将传统阅卷 JSON 映射为报告页可消费的字段（保留中文原键）。"""
    payload = dict(raw)

    final_block = payload.get("最终得分")
    if isinstance(final_block, dict):
        score = final_block.get("分数")
        try:
            if score is not None:
                payload["total_score"] = float(score)
        except (TypeError, ValueError):
            pass
        calc = str(final_block.get("计算说明") or "").strip()
        if calc and not payload.get("review_notes"):
            payload["review_notes"] = calc

    tier = payload.get("档次判定")
    if isinstance(tier, dict):
        tier_label = str(tier.get("档次") or "").strip()
        interval = str(tier.get("分数区间") or "").strip()
        reason = str(tier.get("定档理由") or "").strip()
        parts = [p for p in (tier_label, interval, reason) if p]
        if parts:
            note = "；".join(parts)
            existing = str(payload.get("review_notes") or "").strip()
            payload["review_notes"] = f"{existing}\n{note}".strip() if existing else note
        if tier_label:
            payload["essay_tier_label"] = tier_label

    reasons = payload.get("评分理由")
    if isinstance(reasons, list) and reasons:
        lines = [str(x).strip() for x in reasons if str(x).strip()]
        if lines:
            block = "\n".join(f"· {ln}" for ln in lines)
            existing = str(payload.get("review_notes") or "").strip()
            payload["review_notes"] = f"{existing}\n{block}".strip() if existing else block

    suggestions = payload.get("改进建议")
    if isinstance(suggestions, list) and suggestions and not payload.get("suggestions"):
        payload["suggestions"] = [str(s).strip() for s in suggestions if str(s).strip()][:8]

    hard = payload.get("硬伤筛查")
    if isinstance(hard, dict) and not payload.get("issues"):
        issues: list[dict[str, Any]] = []
        if hard.get("是否触发四类"):
            triggers = hard.get("触发项") or []
            trig_text = "、".join(str(t) for t in triggers) if triggers else ""
            explanation = str(hard.get("说明") or trig_text or "触发四类文硬伤筛查").strip()
            issues.append(
                {
                    "tag": "Q1 硬伤",
                    "severity": "severe",
                    "explanation": explanation,
                    "user_quote": "",
                }
            )
        payload["issues"] = issues

    unknown = payload.get("无法判断项")
    if isinstance(unknown, list) and unknown:
        payload["manual_review_items"] = [str(x).strip() for x in unknown if str(x).strip()]

    payload["traditional_marking"] = raw
    return payload
