from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.essay import essay_length_ratio, official_essay_char_count
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.essay_context import EssayGradingContext


@dataclass
class GateDecision:
    passed: bool
    reason: str = ""
    word_ratio: float = 1.0
    short_circuit_payload: dict[str, Any] | None = None


def run_input_gate(ctx: "EssayGradingContext", content: str) -> GateDecision:
    text = content.strip()
    word_min, word_max = _word_bounds(ctx)
    char_count = official_essay_char_count(text)
    word_ratio = essay_length_ratio(char_count, word_min)
    if char_count < 10:
        return GateDecision(False, "作文过短", word_ratio, _short_payload(ctx, "作文过短", word_ratio))
    if word_ratio < 0.3:
        reason = f"字数不足（低于建议字数 {word_min} 字的约 30%）"
        return GateDecision(False, reason, word_ratio, _short_payload(ctx, reason, word_ratio))
    if not ctx.prompt.strip() and not (ctx.reference_material or "").strip():
        return GateDecision(False, "缺少题干或材料", word_ratio)
    return GateDecision(True, word_ratio=word_ratio)


def _word_bounds(ctx: "EssayGradingContext") -> tuple[int, int]:
    from app.services.essay_context import word_bounds_for_context

    return word_bounds_for_context(ctx)


def _short_payload(ctx: "EssayGradingContext", reason: str, word_ratio: float) -> dict[str, Any]:
    return {
        "total_score": 0,
        "score_range": [0, 0],
        "confidence": "low",
        "consensus_rate": 0,
        "display_mode": "reference_only",
        "short_circuit_reason": reason,
        "word_ratio": word_ratio,
        "scoring_points": [],
        "issues": [],
        "suggestions": ["请按大作文字数与结构要求重写后再提交批改。"],
        "rule_score": 0,
        "llm_score": 0,
    }
