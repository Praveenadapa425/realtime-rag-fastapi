import asyncio
import json
import logging
import aiofiles
import redis.asyncio as redis
from app.config import settings
from app.utils import chunk_text
from app.rag.embeddings import generate_embedding
from app.core.vector_db import collection

logger = logging.getLogger(__name__)

async def process_document(path: str, filename: str) -> None:
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
        
        # Read file asynchronously
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            text = await f.read()
        
        logger.info(f"📖 Read {len(text)} characters from {filename}")
        
        # Split into chunks
        chunks = chunk_text(text, chunk_size=300)
        logger.info(f"📚 Split into {len(chunks)} chunks")
        
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
        collection.add(
            documents=documents,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        
        logger.info(f"✅ Successfully processed {filename} - {len(chunks)} chunks stored in ChromaDB")
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {path}")
    except Exception as e:
        logger.error(f"❌ Error processing {filename}: {str(e)}", exc_info=True)

async def worker() -> None:
    """
    Main worker process:
    1. Connect to Redis
    2. Subscribe to ingestion_queue channel
    3. Listen for document upload messages
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
        
        # Subscribe to ingestion queue
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("ingestion_queue")
        
        logger.info("👂 Worker listening for ingestion tasks...")
        
        # Listen for messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    path = data.get("path")
                    filename = data.get("filename")
                    
                    if path and filename:
                        await process_document(path, filename)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse message: {str(e)}")
                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
    
    except Exception as e:
        logger.error(f"❌ Worker error: {str(e)}", exc_info=True)
        await redis_client.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run worker
    asyncio.run(worker())
