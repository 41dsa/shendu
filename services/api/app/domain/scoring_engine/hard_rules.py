"""A 档硬标准：字数、结构、跑题信号、机械摘抄材料等确定性检测。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.essay import official_essay_char_count
from app.domain.scoring_engine.text_utils import split_paragraphs


@dataclass
class HardRuleReport:
    word_count: int
    word_ratio: float
    paragraph_count: int
    has_title_line: bool
    main_thesis_signal: bool
    severe_off_topic: bool
    mechanical_copy_ratio: float
    format_issues: list[str] = field(default_factory=list)
    flags: dict[str, bool] = field(default_factory=dict)


def _detect_title_line(text: str) -> bool:
    lines = [ln.strip() for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        return False
    first = lines[0]
    if len(first) <= 22 and not re.search(r"[。！？；，]", first):
        return True
    return False


def _mechanical_copy_ratio(essay: str, reference_material: str) -> float:
    ref = (reference_material or "").strip()
    if len(ref) < 80:
        return 0.0
    essay_norm = re.sub(r"\s+", "", essay)
    ref_norm = re.sub(r"\s+", "", ref)
    if len(essay_norm) < 100:
        return 0.0
    window = 24
    if len(ref_norm) < window:
        return 0.0
    hits = 0
    windows = 0
    for i in range(0, len(ref_norm) - window, window // 2):
        chunk = ref_norm[i : i + window]
        windows += 1
        if chunk in essay_norm:
            hits += 1
    return hits / max(windows, 1)


def _genre_issue(task: str, essay: str) -> str | None:
    task_l = (task or "").lower()
    head = essay[:400]
    if "讲话" in task or "发言" in task:
        if "同志们" not in head and "各位" not in head:
            return "题干要求讲话/发言体，开篇缺少常见称谓"
    if "书信" in task or "信函" in task:
        if "此致" not in essay and "敬祝" not in essay:
            return "题干要求书信体，未见常见书信用语"
    if "评论" in task and "笔者认为" not in essay and "总之" not in essay[-200:]:
        return "评论体论证收束偏弱（启发式）"
    return None


def _identity_issue(task: str, essay: str) -> str | None:
    task = task or ""
    m = re.search(r"以(.{2,12})身份", task)
    if not m:
        m = re.search(r"(.{2,8})身份", task)
    if not m:
        return None
    role = m.group(1)
    if role and role not in essay[:500]:
        return f"题干设定身份/对象「{role}」，开篇未见相应自称或对象"
    return None


def _scope_issue(essay: str, must_avoid: list[str], must_address: list[str]) -> str | None:
    for bad in must_avoid:
        token = (bad or "").strip()
        if len(token) >= 2 and token in essay:
            return f"触及命题要求避免的表述：{token[:24]}"
    if must_address:
        hits = sum(1 for m in must_address if len((m or "").strip()) >= 2 and m.strip() in essay)
        if hits == 0 and len(must_address) >= 2:
            return "未见题目要求必须回应的核心要点（范围硬规则）"
    return None


def _typo_heuristic(essay: str) -> tuple[bool, str | None]:
    if essay.count("的的") >= 3 or essay.count("。。。") >= 2:
        return True, "重复用词或标点明显（语病启发式）"
    return False, None


def run_hard_rules(
    essay: str,
    *,
    word_min: int,
    word_max: int,
    reference_material: str = "",
    main_point_hit: bool,
    proposition_task: str = "",
    must_avoid: list[str] | None = None,
    must_address: list[str] | None = None,
) -> HardRuleReport:
    paragraphs = split_paragraphs(essay)
    word_count = official_essay_char_count(essay)
    word_ratio = word_count / max(word_min, 1)
    copy_ratio = _mechanical_copy_ratio(essay, reference_material)
    format_issues: list[str] = []
    if word_ratio < 0.8:
        format_issues.append("字数低于建议下限的 80%")
    if word_ratio > 1.25 and word_max > 0:
        format_issues.append("字数明显超出建议上限")
    if len(paragraphs) < 3:
        format_issues.append("段落过少，结构不完整")
    if copy_ratio >= 0.35:
        format_issues.append("疑似大段机械摘抄给定材料")

    genre_msg = _genre_issue(proposition_task, essay)
    if genre_msg:
        format_issues.append(genre_msg)
    identity_msg = _identity_issue(proposition_task, essay)
    if identity_msg:
        format_issues.append(identity_msg)
    typo_flag, typo_msg = _typo_heuristic(essay)
    if typo_msg:
        format_issues.append(typo_msg)
    scope_msg = _scope_issue(essay, list(must_avoid or []), list(must_address or []))
    if scope_msg:
        format_issues.append(scope_msg)

    severe_off_topic = not main_point_hit
    flags = {
        "word_short": word_ratio < 0.6,
        "word_low": word_ratio < 0.8,
        "structure_incomplete": len(paragraphs) < 3,
        "mechanical_copy": copy_ratio >= 0.35,
        "severe_off_topic": severe_off_topic,
        "genre_mismatch": bool(genre_msg),
        "identity_mismatch": bool(identity_msg),
        "typo_heavy": typo_flag,
        "scope_violation": bool(scope_msg),
    }
    return HardRuleReport(
        word_count=word_count,
        word_ratio=round(word_ratio, 3),
        paragraph_count=len(paragraphs),
        has_title_line=_detect_title_line(essay),
        main_thesis_signal=main_point_hit,
        severe_off_topic=severe_off_topic,
        mechanical_copy_ratio=round(copy_ratio, 3),
        format_issues=format_issues,
        flags=flags,
    )
