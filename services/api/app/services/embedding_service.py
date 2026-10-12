"""OpenAI 兼容 Embedding：用户「Embedding 模型」凭证优先，.env 仅作平台默认。"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.scoring_engine.similarity_provider import SimilarityProvider
from app.domain.scoring_engine.text_utils import split_paragraphs
from app.domain.scoring_engine.types import ScoringPoint
from app.models.entities import CredentialRole, EmbeddingVectorCache, UserProviderCredential
from app.services.ai_client import AiCallError, _upstream_message, decrypt_api_key, get_credential, normalize_base_url

# Chat 基座无 /embeddings 时，须用户单独配置 embedding 凭证
_EMBEDDING_UNSUPPORTED_CHAT_HOSTS = ("api.deepseek.com",)


def _normalize_text(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip())
    return t[: settings.embedding_max_chars_per_text]


def _text_cache_key(text: str, model: str) -> str:
    raw = f"{model}:{_normalize_text(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _valid_http_url(url: str) -> bool:
    p = urlparse(url.strip())
    return p.scheme in ("http", "https") and bool(p.netloc)


def _host_from_url(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _unsupported_chat_host(url: str) -> bool:
    host = _host_from_url(url)
    return any(host == h or host.endswith("." + h) for h in _EMBEDDING_UNSUPPORTED_CHAT_HOSTS)


def embeddings_endpoint(base_or_full_url: str) -> str:
    u = (base_or_full_url or "").strip().rstrip("/")
    if not u:
        return ""
    if u.endswith("/chat/completions"):
        u = u[: -len("/chat/completions")].rstrip("/")
    if u.endswith("/embeddings"):
        return u
    if "/embeddings" in u:
        return u
    base = normalize_base_url(u)
    return base + "/embeddings"


def resolve_embedding_api(db: Session | None, user_id: str | None) -> tuple[str, str, str] | None:
    """
    返回 (url, model, api_key)。
    优先用户「Embedding 模型」配置；否则可选 .env 默认 URL+模型 + 主模型 Key（同厂商场景）。
    主模型为 DeepSeek 等无 embedding 时，必须单独配置 Embedding 凭证。
    """
    if not settings.embedding_enabled:
        return None
    if not db or not user_id:
        return None

    emb_cred = get_credential(db, user_id, CredentialRole.embedding)
    if emb_cred:
        url = embeddings_endpoint(emb_cred.base_url)
        model = (emb_cred.model or "").strip()
        if not url or not model:
            return None
        if not _valid_http_url(url):
            raise AiCallError("CONFIG", f"Embedding Base URL 无效：{url[:120]}")
        return url, model, decrypt_api_key(emb_cred)

    env_url = (settings.embedding_api_url or "").strip()
    env_model = (settings.embedding_model or "").strip()
    if not env_url or not env_model:
        return None

    primary = get_credential(db, user_id, CredentialRole.primary)
    if not primary:
        return None
    if _unsupported_chat_host(primary.base_url) or _unsupported_chat_host(env_url):
        return None

    url = embeddings_endpoint(env_url)
    if not _valid_http_url(url):
        raise AiCallError("CONFIG", f"EMBEDDING_API_URL 无效：{url[:120]}")
    return url, env_model, decrypt_api_key(primary)


def _load_vectors_from_db(db: Session, keys: list[str]) -> dict[str, list[float]]:
    if not keys:
        return {}
    rows = db.query(EmbeddingVectorCache).filter(EmbeddingVectorCache.cache_key.in_(keys)).all()
    out: dict[str, list[float]] = {}
    for row in rows:
        vec = row.vector
        if isinstance(vec, list) and vec:
            out[row.cache_key] = [float(x) for x in vec]
    return out


def _persist_vectors(db: Session, model: str, items: list[tuple[str, list[float]]]) -> None:
    for key, vec in items:
        if not vec:
            continue
        existing = db.query(EmbeddingVectorCache).filter(EmbeddingVectorCache.cache_key == key).first()
        if existing:
            existing.vector = vec
            existing.model = model
        else:
            db.add(EmbeddingVectorCache(cache_key=key, model=model, vector=vec))
    try:
        db.commit()
    except Exception:
        db.rollback()


async def fetch_embeddings_http(
    *,
    url: str,
    api_key: str,
    model: str,
    texts: list[str],
) -> list[list[float]]:
    if not texts:
        return []
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    timeout = httpx.Timeout(connect=10.0, read=settings.embedding_timeout_seconds, write=30.0, pool=10.0)
    vectors: list[list[float]] = []
    batch = max(1, settings.embedding_batch_size)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for i in range(0, len(texts), batch):
            chunk = texts[i : i + batch]
            payload: dict[str, Any] = {"model": model, "input": chunk}
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code >= 400:
                upstream = _upstream_message(resp)
                msg = f"Embedding 调用失败 ({resp.status_code})"
                if upstream:
                    msg += f"：{upstream}"
                raise AiCallError("UPSTREAM", msg)
            data = resp.json()
            rows = data.get("data") or []
            if not rows:
                raise AiCallError("UPSTREAM", "Embedding 响应无 data")
            rows_sorted = sorted(rows, key=lambda r: r.get("index", 0))
            for row in rows_sorted:
                emb = row.get("embedding")
                if not isinstance(emb, list):
                    raise AiCallError("UPSTREAM", "Embedding 格式无效")
                vectors.append([float(x) for x in emb])
    if len(vectors) != len(texts):
        raise AiCallError("UPSTREAM", "Embedding 条数与输入不一致")
    return vectors


def collect_texts_for_matching(essay: str, points: list[ScoringPoint]) -> list[str]:
    texts: set[str] = set()
    for para in split_paragraphs(essay):
        if para.strip():
            texts.add(_normalize_text(para))
    for pt in points:
        for phrase in [pt.text, *pt.semantic_variants, *pt.keywords]:
            if phrase and str(phrase).strip():
                texts.add(_normalize_text(str(phrase)))
    return sorted(texts)


async def build_similarity_provider(
    db: Session | None,
    *,
    user_id: str | None,
    essay: str,
    points: list[ScoringPoint],
) -> SimilarityProvider:
    texts = collect_texts_for_matching(essay, points)
    try:
        resolved = resolve_embedding_api(db, user_id) if db else None
    except AiCallError:
        return SimilarityProvider(backend="local_ngram", model="local")
    if not resolved:
        return SimilarityProvider(backend="local_ngram", model="local")

    url, model, api_key = resolved
    keys = [_text_cache_key(t, model) for t in texts]
    key_by_text = {t: k for t, k in zip(texts, keys, strict=True)}
    vectors: dict[str, list[float]] = {}
    if db:
        vectors.update(_load_vectors_from_db(db, keys))

    missing_texts = [t for t in texts if key_by_text[t] not in vectors]
    if missing_texts:
        try:
            fetched = await fetch_embeddings_http(
                url=url,
                api_key=api_key,
                model=model,
                texts=missing_texts,
            )
            new_items: list[tuple[str, list[float]]] = []
            for t, vec in zip(missing_texts, fetched, strict=True):
                k = key_by_text[t]
                vectors[k] = vec
                new_items.append((k, vec))
            if db and new_items:
                _persist_vectors(db, model, new_items)
        except AiCallError:
            return SimilarityProvider(backend="local_ngram", model="local")

    return SimilarityProvider(
        backend="http_embedding",
        model=model,
        _vectors=vectors,
        _key_by_text=key_by_text,
        _max_chars=settings.embedding_max_chars_per_text,
    )
