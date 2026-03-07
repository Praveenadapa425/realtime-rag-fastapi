import logging
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)


def _collection_name_for_model(model_name: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in model_name)
    normalized = "_".join(part for part in normalized.split("_") if part)
    return f"documents_{normalized}"[:63]

try:
    client = chromadb.Client(
        chromadb.config.Settings(
            persist_directory=settings.VECTOR_DB_PATH,
            is_persistent=True
        )
    )

    collection_name = _collection_name_for_model(settings.EMBEDDING_MODEL)

    def get_collection():
        """Resolve collection lazily to avoid stale handles across long-running processes."""
        return client.get_or_create_collection(name=collection_name)

    # Trigger initialization once on startup for visibility and early failures.
    get_collection()
    
    logger.info(
        "✅ ChromaDB initialized at %s (collection: %s)",
        settings.VECTOR_DB_PATH,
        collection_name,
    )
except Exception as e:
    logger.error(f"❌ Failed to initialize ChromaDB: {str(e)}")
    raise
