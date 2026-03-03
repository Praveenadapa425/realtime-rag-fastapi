import logging
import json
import os
import aiofiles
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.redis import redis_client
from app.schemas import IngestionResponse

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = "uploads"
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".md", ".doc", ".docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

os.makedirs(UPLOAD_DIR, exist_ok=True)

def is_allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    _, ext = os.path.splitext(filename)
    return ext.lower() in ALLOWED_EXTENSIONS

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
        
        # Publish to Redis
        message = {
            "filename": file.filename,
            "path": file_path,
            "size": len(content)
        }
        
        try:
            await redis_client.publish(
                "ingestion_queue",
                json.dumps(message)
            )
            logger.info(f"✅ Published ingestion message for {file.filename}")
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to queue ingestion: {str(e)}")
        
        return IngestionResponse(
            message="Document ingestion initiated",
            filename=file.filename,
            path=file_path
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")