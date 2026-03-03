import logging
import random

logger = logging.getLogger(__name__)

async def generate_embedding(text: str) -> list:
    """
    Generate embedding for text.
    
    Note: This is a temporary mock embedding.
    In production, this will use real embedding models:
    - Ollama local model
    - HuggingFace models
    - OpenAI embeddings
    
    Args:
        text: Input text to embed
    
    Returns:
        List of 384 dimensions (mock embedding)
    """
    # Temporary fake embedding (384 dimension vector)
    # Each run produces different random values for testing
    embedding = [random.random() for _ in range(384)]
    
    logger.debug(f"Generated embedding for text: {text[:50]}...")
    return embedding
