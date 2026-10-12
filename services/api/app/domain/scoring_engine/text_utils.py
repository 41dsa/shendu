from __future__ import annotations

import re
from typing import Callable


def normalize_cn(text: str) -> str:
    t = re.sub(r"\s+", "", (text or "").strip())
    return t.lower()


def split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n+", text.replace("\r", "")) if p.strip()]
    return parts or [text.strip()] if text.strip() else []


def char_bigrams(s: str) -> set[str]:
    s = normalize_cn(s)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def keyword_hit(haystack: str, keywords: list[str]) -> bool:
    h = normalize_cn(haystack)
    for kw in keywords:
        k = normalize_cn(kw)
        if len(k) >= 2 and k in h:
            return True
    return False


def best_paragraph_match(
    essay: str,
    phrases: list[str],
    *,
    similarity_fn: Callable[[str, str], float] | None = None,
) -> tuple[int, str, float]:
    """返回 (段落号1-based, 段落文本, 相似度)。"""
    paragraphs = split_paragraphs(essay)
    best_i, best_p, best_sim = 0, "", 0.0
    for idx, para in enumerate(paragraphs):
        para_sim = 0.0
        for phrase in phrases:
            if not phrase:
                continue
            if keyword_hit(para, [phrase]):
                para_sim = max(para_sim, 0.95)
                continue
            if similarity_fn:
                sim = similarity_fn(para, phrase)
            else:
                sim = jaccard(char_bigrams(para), char_bigrams(phrase))
            para_sim = max(para_sim, sim)
        if para_sim > best_sim:
            best_sim = para_sim
            best_i = idx + 1
            best_p = para
    return best_i, best_p, best_sim
