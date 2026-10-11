"""① 试题解析（大作文）：从 Question 输出结构化考查信息。"""

from __future__ import annotations

from typing import Any

from app.models.entities import Question


def parse_essay_question_metadata(question: Question) -> dict[str, Any]:
    meta = question.material_structured or {}
    exam = str(meta.get("exam") or "")
    year = meta.get("year")
    word_min = int(meta.get("word_min") or 800)
    word_max = int(meta.get("word_max") or question.word_limit or 1200)
    category = ""
    if "副省级" in exam:
        category = "副省级"
    elif "市地级" in exam:
        category = "市地级"
    elif "省考" in exam or "省" in exam:
        category = "省考"
    exam_type = "国考" if "国考" in exam else ("省考" if category == "省考" else exam or "其他")
    return {
        "exam_type": exam_type,
        "category": category or None,
        "question_type": "essay",
        "question_type_label": "大作文",
        "score": int(question.score or 40),
        "word_limit": word_max,
        "word_min": word_min,
        "word_max": word_max,
        "task": (question.prompt or "")[:500],
        "constraints": [
            f"字数建议 {word_min}～{word_max} 字",
            "文体：议论文（方案默认）",
        ],
        "abilities": ["阅读理解", "综合分析", "文字表达"],
    }
