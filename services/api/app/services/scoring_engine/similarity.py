from __future__ import annotations

from app.domain.scoring_engine.embedding import semantic_similarity
from app.domain.scoring_engine.similarity_provider import SimilarityProvider


def default_similarity(a: str, b: str) -> float:
    return semantic_similarity(a, b)


def paragraph_phrase_similarity(
    provider: SimilarityProvider | None,
    paragraph: str,
    phrase: str,
) -> float:
    if provider:
        return provider.similarity(paragraph, phrase)
    return default_similarity(paragraph, phrase)
