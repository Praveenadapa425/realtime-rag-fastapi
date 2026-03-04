import logging
import json
import os
import hashlib
import uuid
from datetime import datetime, timezone
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.redis import redis_client
from app.schemas import IngestionResponse, IngestionStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter()

INGESTION_QUEUE_KEY = "ingestion_queue"
INGESTION_STATUS_PREFIX = "ingestion_status"
UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".md", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS


def _status_key(task_id: str) -> str:
    return f"{INGESTION_STATUS_PREFIX}:{task_id}"

@router.post("/ingest", response_model=IngestionResponse)
async def ingest_document(file: UploadFile = File(...)):
    """
    Upload and ingest a document for processing
    - Validates file type and size
    - Stores file asynchronously
    - Publishes ingestion event to Redis
    """
    try:
        # Validate file
        if not file.filename:
            logger.warning("Ingest attempt with no filename")
            raise HTTPException(status_code=400, detail="Filename is required")
        
        if not is_allowed_file(file.filename):
            logger.warning(f"Attempt to upload disallowed file type: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )
        
        # Read and validate file size
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"File too large: {file.filename} - {len(content)} bytes")
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Save file asynchronously
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        try:
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            logger.info(f"✅ File saved: {file_path}")
        except IOError as e:
            logger.error(f"Failed to save file {file_path}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
        # Push task to durable Redis queue
        task_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(content).hexdigest()
        message = {
            "task_id": task_id,
            "filename": file.filename,
            "path": file_path,
            "size": len(content),
            "content_hash": content_hash,
            "retries": 0,
        }
        
        try:
            queue_size = await redis_client.rpush(INGESTION_QUEUE_KEY, json.dumps(message))
            await redis_client.hset(
                _status_key(task_id),
                mapping={
                    "task_id": task_id,
                    "filename": file.filename,
                    "status": "queued",
                    "message": f"Queued for indexing (position ~{queue_size})",
                    "retries": 0,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            await redis_client.expire(_status_key(task_id), 60 * 60 * 24)
            logger.info(f"✅ Queued ingestion task for {file.filename} (queue size: {queue_size})")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to queue ingestion: {str(e)}")
        
        return IngestionResponse(
            message="Document ingestion queued",
            filename=file.filename,
            path=file_path,
            task_id=task_id,
            status="queued",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/ingest/status/{task_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(task_id: str):
    try:
        raw_status = await redis_client.hgetall(_status_key(task_id))
        if not raw_status:
            raise HTTPException(status_code=404, detail="Ingestion task not found")

        retries = int(raw_status.get("retries", 0))
        return IngestionStatusResponse(
            task_id=raw_status.get("task_id", task_id),
            filename=raw_status.get("filename", "unknown"),
            status=raw_status.get("status", "unknown"),
            message=raw_status.get("message"),
            retries=retries,
            updated_at=raw_status.get("updated_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch ingestion status {task_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch status: {str(e)}")