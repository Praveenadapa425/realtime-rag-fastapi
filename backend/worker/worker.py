import asyncio
import json
import logging
from pathlib import Path
import aiofiles
import redis.asyncio as redis
from docx import Document
from pypdf import PdfReader
from app.config import settings
from app.utils import chunk_text
from app.rag.embeddings import generate_embedding
from app.core.vector_db import collection

logger = logging.getLogger(__name__)
INGESTION_QUEUE_KEY = "ingestion_queue"
PROCESSED_SET_KEY = "ingestion_processed"
DEAD_LETTER_QUEUE_KEY = "ingestion_dead_letter"
MAX_RETRIES = 3


def _extract_pdf_text(path: str) -> str:
    reader = PdfReader(path)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _extract_docx_text(path: str) -> str:
    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


async def _extract_text(path: str) -> str:
    extension = Path(path).suffix.lower()

    if extension in {".txt", ".md"}:
        async with aiofiles.open(path, "r", encoding="utf-8") as file:
            return await file.read()

    if extension == ".pdf":
        return await asyncio.to_thread(_extract_pdf_text, path)

    if extension == ".docx":
        return await asyncio.to_thread(_extract_docx_text, path)

    raise ValueError(f"Unsupported file extension for extraction: {extension}")

async def process_document(path: str, filename: str) -> bool:
    """
    Process uploaded document:
    1. Read file
    2. Split into chunks
    3. Generate embeddings
    4. Store in ChromaDB
    
    Args:
        path: File path
        filename: Original filename
    """
    try:
        logger.info(f"📄 Processing document: {filename}")
        
        text = await _extract_text(path)
        
        logger.info(f"📖 Read {len(text)} characters from {filename}")

        if not text.strip():
            logger.warning(f"⚠️ No extractable text found in {filename}")
            return False
        
        # Split into chunks
        chunks = chunk_text(text, chunk_size=300)
        logger.info(f"📚 Split into {len(chunks)} chunks")

        if not chunks:
            logger.warning(f"⚠️ No chunks generated for {filename}")
            return False
        
        # Process each chunk
        documents = []
        embeddings = []
        ids = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = await generate_embedding(chunk)
            
            # Prepare data for storage
            documents.append(chunk)
            embeddings.append(embedding)
            ids.append(f"{filename}_{i}")
            metadatas.append({
                "source": filename,
                "chunk": i,
                "length": len(chunk)
            })
        
        # Store in ChromaDB
        await asyncio.to_thread(
            collection.add,
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )
        
        logger.info(f"✅ Successfully processed {filename} - {len(chunks)} chunks stored in ChromaDB")
        return True
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {path}")
        return False
    except Exception as e:
        logger.error(f"❌ Error processing {filename}: {str(e)}", exc_info=True)
        return False

async def worker() -> None:
    """
    Main worker process:
    1. Connect to Redis
    2. Block on durable ingestion queue key
    3. Consume document upload messages
    4. Process documents asynchronously
    """
    logger.info("🤖 Starting worker process...")
    
    try:
        # Connect to Redis
        redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True
        )
        
        # Test connection
        await redis_client.ping()
        logger.info("✅ Connected to Redis")
        
        logger.info("👂 Worker waiting on durable ingestion queue...")

        while True:
            try:
                message = await redis_client.blpop(INGESTION_QUEUE_KEY, timeout=5)
                if message is None:
                    continue

                _, payload = message
                data = json.loads(payload)
                path = data.get("path")
                filename = data.get("filename")
                content_hash = data.get("content_hash")
                retries = int(data.get("retries", 0))

                idempotency_key = f"{filename}:{content_hash}" if content_hash else filename

                if await redis_client.sismember(PROCESSED_SET_KEY, idempotency_key):
                    logger.info("↩️ Skipping already processed document: %s", filename)
                    continue

                if path and filename:
                    success = await process_document(path, filename)
                    if success:
                        await redis_client.sadd(PROCESSED_SET_KEY, idempotency_key)
                    elif retries < MAX_RETRIES:
                        data["retries"] = retries + 1
                        await redis_client.rpush(INGESTION_QUEUE_KEY, json.dumps(data))
                        logger.warning(
                            "Retrying %s (%d/%d)",
                            filename,
                            retries + 1,
                            MAX_RETRIES,
                        )
                    else:
                        await redis_client.rpush(DEAD_LETTER_QUEUE_KEY, json.dumps(data))
                        logger.error("Moved failed task to dead-letter queue: %s", filename)
                else:
                    logger.warning("Skipping queue message with missing path/filename")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse message: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}", exc_info=True)
    
    except Exception as e:
        logger.error(f"❌ Worker error: {str(e)}", exc_info=True)
    finally:
        await redis_client.aclose()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run worker
    asyncio.run(worker())
