"""申论大作文（V1 唯一批改对象）领域常量与辅助函数。"""

import re
from typing import Any

ESSAY_GENRE = "essay"
QUESTION_TYPE_LABEL = "申论大作文"

# 用户自备题干/材料批改时绑定的占位题库 ID（实际文本存在 submission 字段）
USER_ESSAY_QUESTION_ID = "sys-user-essay"
DEMO_QUESTION_ID = "demo-essay-001"

# 报告 JSON 中维度列表字段（与历史 API 兼容）
RUBRIC_JSON_KEY = "scoring_points"

# V1 启用的 5 个能力维（对应 PRD V1.2-E §6）
ABILITY_DIMENSIONS: list[dict[str, str]] = [
    {"id": "A1", "name": "立意与审题"},
    {"id": "A2", "name": "结构与层次"},
    {"id": "A3", "name": "论证与素材"},
    {"id": "A4", "name": "语言表达"},
    {"id": "A5", "name": "规范与字数"},
]

# 大作文优先问题标签（PRD §9 子集）
ESSAY_ISSUE_TAGS: list[dict[str, str]] = [
    {"code": "Q21", "label": "立意偏差", "ability": "A1"},
    {"code": "Q25", "label": "结构失衡", "ability": "A2"},
    {"code": "Q22", "label": "分论点弱", "ability": "A2"},
    {"code": "Q24", "label": "论证不足", "ability": "A3"},
    {"code": "Q23", "label": "论据不足", "ability": "A3"},
    {"code": "Q17", "label": "语言不规范", "ability": "A4"},
    {"code": "Q20", "label": "字数问题", "ability": "A5"},
]

DEFAULT_RUBRIC_DIMENSIONS: list[dict[str, Any]] = [
    {"id": "D01", "label": "立意与观点", "max_score": 10, "required": True, "ability": "A1"},
    {"id": "D02", "label": "结构与层次", "max_score": 10, "required": True, "ability": "A2"},
    {"id": "D03", "label": "论证与素材", "max_score": 10, "required": True, "ability": "A3"},
    {"id": "D04", "label": "语言表达", "max_score": 10, "required": True, "ability": "A4"},
]


def essay_word_bounds(question_meta: dict[str, Any] | None, word_limit: int) -> tuple[int, int]:
    meta = question_meta or {}
    word_min = int(meta.get("word_min") or max(800, int(word_limit * 0.67)))
    word_max = int(meta.get("word_max") or word_limit)
    return word_min, word_max


def essay_length_ratio(char_count: int, word_min: int) -> float:
    return char_count / max(word_min, 1)


def issue_tag_prompt_hint() -> str:
    return "、".join(f"{t['code']} {t['label']}" for t in ESSAY_ISSUE_TAGS)


_ISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Q21": ("立意", "偏题", "题意", "审题"),
    "Q25": ("结构", "层次", "递进", "重复", "交叉"),
    "Q22": ("分论点", "论点弱"),
    "Q24": ("论证", "因果", "分析不足", "对策为主"),
    "Q23": ("论据", "案例", "数据", "素材", "材料", "联系实际"),
    "Q17": ("语言", "口号", "模板", "病句", "错别字"),
    "Q20": ("字数", "篇幅", "不足", "达标"),
}


def resolve_issue_badge(problem: str, raw_tag: str | None = None) -> str:
    """短标签「Q24 论证不足」；长分析应放在 explanation。"""
    if raw_tag:
        m = re.match(r"^(Q\d+)\s*(.*)$", raw_tag.strip(), re.I)
        if m:
            code = m.group(1).upper()
            for t in ESSAY_ISSUE_TAGS:
                if t["code"] == code:
                    return f"{t['code']} {t['label']}"
            rest = (m.group(2) or "").strip()
            return f"{code} {rest}".strip()
    text = f"{problem} {raw_tag or ''}"
    for t in ESSAY_ISSUE_TAGS:
        code = t["code"]
        if any(kw in text for kw in _ISSUE_KEYWORDS.get(code, ())):
            return f"{t['code']} {t['label']}"
    return "作答问题"


def label_to_ability(label: str) -> str:
    """Rubric 维度名称 → 能力维 ID（A1～A5）。"""
    if "立意" in label or "观点" in label:
        return "A1"
    if "结构" in label:
        return "A2"
    if "论证" in label or "素材" in label:
        return "A3"
    if "语言" in label:
        return "A4"
    if "字数" in label or "规范" in label:
        return "A5"
    return "A1"
