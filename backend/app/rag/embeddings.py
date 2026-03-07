import logging
import hashlib
import random
import asyncio
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_DIM = 768


def _resolved_fallback_dim() -> int:
    configured = int(getattr(settings, "FALLBACK_EMBEDDING_DIM", DEFAULT_FALLBACK_DIM) or DEFAULT_FALLBACK_DIM)
    if configured > 0:
        return configured
    return DEFAULT_FALLBACK_DIM


def _deterministic_fallback_embedding(text: str, dimensions: int = DEFAULT_FALLBACK_DIM) -> List[float]:
    """Generate deterministic fallback embeddings based on text hash."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]


async def _ollama_embedding(text: str) -> List[float]:
    """Fetch an embedding from Ollama using the configured embedding model."""
    base_url = settings.OLLAMA_BASE_URL.rstrip("/")
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=30.0)

    attempts = 2
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, attempts + 1):
            try:
                embed_url = f"{base_url}/api/embed"
                embed_payload = {
                    "model": settings.EMBEDDING_MODEL,
                    "input": text,
                }
                embed_response = await client.post(embed_url, json=embed_payload)
                if embed_response.status_code < 400:
                    embed_data = embed_response.json()
                    embeddings = embed_data.get("embeddings")
                    if isinstance(embeddings, list) and embeddings and isinstance(embeddings[0], list):
                        return embeddings[0]

                legacy_url = f"{base_url}/api/embeddings"
                legacy_payload = {
                    "model": settings.EMBEDDING_MODEL,
                    "prompt": text,
                }
                legacy_response = await client.post(legacy_url, json=legacy_payload)
                legacy_response.raise_for_status()
                legacy_data = legacy_response.json()

                embedding = legacy_data.get("embedding")
                if not isinstance(embedding, list) or not embedding:
                    raise ValueError("Invalid embedding payload from Ollama")

                return embedding
            except httpx.ConnectError:
                if attempt >= attempts:
                    raise
                await asyncio.sleep(1.0)


async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text.

    Primary path uses local Ollama embeddings.
    If Ollama/model is unavailable, falls back to deterministic embeddings
    to keep ingestion/retrieval flows operational in local development.
    
    Args:
        text: Input text to embed

    Returns:
        Embedding vector as list of floats
    """
    normalized_text = (text or "").strip()
    fallback_dim = _resolved_fallback_dim()
    if not normalized_text:
        return [0.0] * fallback_dim

    try:
        embedding = await _ollama_embedding(normalized_text)
        logger.debug(f"Generated Ollama embedding with {len(embedding)} dims")
        return embedding
    except Exception as exc:
        logger.warning(
            "Falling back to deterministic embedding: %s",
            str(exc),
        )
        return _deterministic_fallback_embedding(normalized_text, dimensions=fallback_dim)
