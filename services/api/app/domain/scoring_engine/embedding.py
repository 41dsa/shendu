"""中文语义向量（本地 char-ngram TF，无外部模型依赖；可替换为 BGE 服务）。"""

from __future__ import annotations

import math
import re
from collections import Counter


def _tokenize(text: str) -> list[str]:
    t = re.sub(r"\s+", "", text or "")
    grams: list[str] = []
    for n in (2, 3, 4):
        for i in range(len(t) - n + 1):
            grams.append(t[i : i + n])
    return grams or ([t] if t else [])


def term_vector(text: str) -> Counter[str]:
    tokens = _tokenize(text)
    return Counter(tokens)


def cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a[k] * b[k] for k in a if k in b)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def semantic_similarity(text_a: str, text_b: str) -> float:
    return cosine_similarity(term_vector(text_a), term_vector(text_b))


def cosine_similarity_dense(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
