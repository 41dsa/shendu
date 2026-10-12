"""Embedding 网关与 SimilarityProvider 冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.embedding import cosine_similarity_dense, semantic_similarity
from app.domain.scoring_engine.similarity_provider import SimilarityProvider
from app.services.embedding_service import collect_texts_for_matching, embeddings_endpoint, resolve_embedding_api


def test_local_similarity() -> None:
    a = "推进基层治理现代化"
    b = "基层治理的现代化路径"
    assert semantic_similarity(a, b) > 0.05


def test_dense_vectors() -> None:
    assert cosine_similarity_dense([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_provider_http_shape() -> None:
    p = SimilarityProvider(
        backend="http_embedding",
        model="test",
        _vectors={"k1": [1.0, 0.0], "k2": [0.9, 0.1]},
        _key_by_text={"hello": "k1", "hi": "k2"},
    )
    assert p.similarity("hello", "hi") > 0.9


def test_endpoint_normalization() -> None:
    assert embeddings_endpoint("https://api.example.com/v1").endswith("/embeddings")
    assert embeddings_endpoint(
        "https://maas.qianwenaiapi.com/compatible-mode/v1/chat/completions"
    ).endswith("/embeddings")


def test_resolve_without_db() -> None:
    assert resolve_embedding_api(None, None) is None


def test_collect_texts() -> None:
    from app.domain.scoring_engine.types import ScoringPoint

    pts = [ScoringPoint(point_id="P1", text="基层治理", dimension_id="D01", keywords=["治理"])]
    texts = collect_texts_for_matching("第一段\n第二段", pts)
    assert len(texts) >= 2


def main() -> None:
    test_local_similarity()
    test_dense_vectors()
    test_provider_http_shape()
    test_endpoint_normalization()
    test_resolve_without_db()
    test_collect_texts()
    print("verify_embedding_service: ok")


if __name__ == "__main__":
    main()
