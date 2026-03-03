import logging
import chromadb
from app.config import settings

logger = logging.getLogger(__name__)

try:
    client = chromadb.Client(
        chromadb.config.Settings(
            persist_directory=settings.VECTOR_DB_PATH,
            is_persistent=True
        )
    )
    
    collection = client.get_or_create_collection(
        name="documents"
    )
    
    logger.info(f"✅ ChromaDB initialized at {settings.VECTOR_DB_PATH}")
except Exception as e:
    logger.error(f"❌ Failed to initialize ChromaDB: {str(e)}")
    raise
