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


# 方格纸计字：单格标点 +1，双格标点 +2（与前端 essayCharCount.ts 一致）
_SINGLE_GRID_PUNCT = frozenset("，。；：？！、")
_DOUBLE_GRID_CHARS = frozenset("《》（）\u201c\u201d\u2018\u2019")


_HAN_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _is_title_line_for_shenlun_count(line: str) -> bool:
    """仅识别短独立标题行，避免把正文首句（含逗号、长句）误判为标题。"""
    t = line.strip()
    if not t:
        return False
    if re.match(r"^#{1,6}\s+\S", t):
        return True
    if re.match(r"^[\u3000 ]{1,2}", line):
        return False
    body = re.sub(r"^#{1,6}\s+", "", t)
    han = len(_HAN_CHAR_RE.findall(body))
    if han == 0:
        return False
    if len(body) > 22 or re.search(r"[。！？；]", body):
        return False
    if "，" in body or "," in body:
        return False
    if re.search(r"[是在的有与为以这那]", body):
        return False
    return 2 <= han <= 18


def essay_body_text_excluding_title(text: str) -> str:
    """去掉文首自拟/独立标题行，保留正文（含段首缩进）。"""
    if not text:
        return ""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    skip: set[int] = set()
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        if _is_title_line_for_shenlun_count(line):
            skip.add(idx)
        break
    return "\n".join(line for i, line in enumerate(lines) if i not in skip)


def count_shenlun_body_han_chars(text: str) -> int:
    """正文汉字数（不含标点）。"""
    body = essay_body_text_excluding_title(text)
    return len(_HAN_CHAR_RE.findall(body))


def count_shenlun_body_chars(text: str) -> int:
    """
    申论正文字数：不计空格/换行、不计文首标题；
    正文其余字符均计（汉字、数字、字母及中英文标点等）。
    """
    body = essay_body_text_excluding_title(text)
    return sum(1 for ch in body if not ch.isspace())


def count_essay_chars(text: str) -> int:
    """
    申论作文字数（方格纸）：
    - 汉字、阿拉伯数字、英文字母等按实际占格各计 1（如「123」为 3 字，「abc」为 3 字）；
    - 空白不计；
    - 单格标点（，。；：？！、等）计 1；双格标点（——、……、书名号、引号、括号等）计 2。
    """
    if not text:
        return 0
    s = text.replace("\r\n", "\n").replace("\r", "\n")
    total = 0
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch in " \t\n":
            i += 1
            continue
        if s.startswith("……", i):
            total += 2
            i += 2
            continue
        if s.startswith("——", i):
            total += 2
            i += 2
            continue
        if ch == "…":
            j = i
            while j < n and s[j] == "…":
                j += 1
            total += 2
            i = j
            continue
        if ch == "—":
            if i + 1 < n and s[i + 1] == "—":
                total += 2
                i += 2
            else:
                total += 2
                i += 1
            continue
        if ch in _DOUBLE_GRID_CHARS:
            total += 2
            i += 1
            continue
        if ch in _SINGLE_GRID_PUNCT or ch in ",.;:?!":
            total += 1
            i += 1
            continue
        total += 1
        i += 1
    return total


def essay_length_ratio_from_text(text: str, word_min: int) -> float:
    return essay_length_ratio(count_shenlun_body_han_chars(text), word_min)


def official_essay_char_count(text: str) -> int:
    """批改、字数门槛、报告展示统一用申论正文字数。"""
    return count_shenlun_body_chars(text)


def issue_tag_prompt_hint() -> str:
    return "、".join(f"{t['code']} {t['label']}" for t in ESSAY_ISSUE_TAGS)


_ISSUE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Q21": ("立意", "偏题", "题意", "审题"),
    "Q25": ("结构", "层次", "递进", "重复", "交叉"),
    "Q22": ("分论点", "论点弱"),
    "Q24": ("论证", "因果", "分析不足", "对策为主"),
    "Q23": ("论据", "案例", "数据", "素材", "材料", "联系实际"),
    "Q17": ("语言", "口号", "模板", "病句", "错别字"),
    "Q20": ("字数不足", "篇幅不足", "字数偏少", "未达字数", "字数未", "低于建议字数", "字数", "篇幅"),
}


def normalize_issue_code(raw: str | None) -> str:
    """从「Q21 立意偏差」提取稳定键 Q21；无法识别时返回空串。"""
    if not raw:
        return ""
    token = raw.strip().split()[0]
    if re.match(r"^Q\d+$", token, re.I):
        return token.upper()
    return ""


def issue_label_for_code(code: str) -> str | None:
    c = code.upper()
    for t in ESSAY_ISSUE_TAGS:
        if t["code"] == c:
            return t["label"]
    return None


def ability_for_issue_code(code: str) -> str | None:
    c = code.upper()
    for t in ESSAY_ISSUE_TAGS:
        if t["code"] == c:
            return t["ability"]
    return None


def ability_for_issue_tag(raw_tag: str | None) -> str | None:
    code = normalize_issue_code(raw_tag)
    if code:
        return ability_for_issue_code(code)
    return None


def issue_tag_from_core_problem(title: str, problem: str) -> str:
    """core_problems 条目：优先用 title 归类，避免长 problem 误触「论据/论证」等关键词。"""
    for text in (title, problem):
        t = text.strip()
        if not t:
            continue
        for row in ESSAY_ISSUE_TAGS:
            code = row["code"]
            kws = _ISSUE_KEYWORDS.get(code, ())
            if any(kw in t for kw in kws):
                return f"{row['code']} {row['label']}"
        short = resolve_issue_badge(t, None)
        if short and short != "作答问题":
            return short
    if title.strip():
        return title.strip()[:16]
    return resolve_issue_badge(problem, None) if problem else "作答问题"


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
