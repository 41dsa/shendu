"""申论大作文（V1 唯一批改对象）领域常量与辅助函数。"""

from typing import Any

ESSAY_GENRE = "essay"

# 报告与 Prompt 中沿用的 JSON 字段名（历史兼容）
RUBRIC_JSON_KEY = "scoring_points"


def essay_word_bounds(question_meta: dict[str, Any] | None, word_limit: int) -> tuple[int, int]:
    meta = question_meta or {}
    word_min = int(meta.get("word_min") or max(800, int(word_limit * 0.67)))
    word_max = int(meta.get("word_max") or word_limit)
    return word_min, word_max


def essay_length_ratio(char_count: int, word_min: int) -> float:
    return char_count / max(word_min, 1)
