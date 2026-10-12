from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.scoring_engine.embedding import cosine_similarity_dense, semantic_similarity


def _normalize_text(text: str, max_chars: int = 2048) -> str:
    t = " ".join((text or "").split())
    return t[:max_chars]


@dataclass
class SimilarityProvider:
    backend: str
    model: str
    _vectors: dict[str, list[float]] = field(default_factory=dict)
    _key_by_text: dict[str, str] = field(default_factory=dict)
    _max_chars: int = 2048

    def similarity(self, text_a: str, text_b: str) -> float:
        a = _normalize_text(text_a, self._max_chars)
        b = _normalize_text(text_b, self._max_chars)
        if not a or not b:
            return 0.0
        if self.backend == "http_embedding":
            ka = self._key_by_text.get(a)
            kb = self._key_by_text.get(b)
            if ka and kb and ka in self._vectors and kb in self._vectors:
                return cosine_similarity_dense(self._vectors[ka], self._vectors[kb])
        return semantic_similarity(a, b)
