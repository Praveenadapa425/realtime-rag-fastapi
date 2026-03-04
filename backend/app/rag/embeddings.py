import logging
import hashlib
import random
from typing import List

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_FALLBACK_DIM = 384


def _deterministic_fallback_embedding(text: str, dimensions: int = DEFAULT_FALLBACK_DIM) -> List[float]:
    """Generate deterministic fallback embeddings based on text hash."""
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]


async def _ollama_embedding(text: str) -> List[float]:
    """Fetch an embedding from Ollama using the configured embedding model."""
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings"
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "prompt": text,
    }

    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    embedding = data.get("embedding")
    if not isinstance(embedding, list) or not embedding:
        raise ValueError("Invalid embedding payload from Ollama")

    return embedding


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
    if not normalized_text:
        return [0.0] * DEFAULT_FALLBACK_DIM

    try:
        embedding = await _ollama_embedding(normalized_text)
        logger.debug(f"Generated Ollama embedding with {len(embedding)} dims")
        return embedding
    except Exception as exc:
        logger.warning(
            "Falling back to deterministic embedding: %s",
            str(exc),
        )
        return _deterministic_fallback_embedding(normalized_text)
