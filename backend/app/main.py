import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.websocket import router as websocket_router
from app.ingestion import router as ingestion_router
from app.core.redis import redis_client
from app.schemas import HealthCheckResponse
from app.config import settings
from app.rag.generator import warmup_ollama

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize and clean up app resources."""
    try:
        await redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {str(e)}")

    try:
        await warmup_ollama()
    except Exception as e:
        logger.warning(f"Ollama warmup not completed: {str(e)}")

    try:
        yield
    finally:
        try:
            await redis_client.aclose()
            logger.info("✅ Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis: {str(e)}")


app = FastAPI(
    title="Realtime RAG FastAPI",
    description="Real-time Retrieval Augmented Generation with streaming",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthCheckResponse)
async def health():
    """Health check endpoint with Redis connectivity verification"""
    try:
        # Check Redis connection
        redis_status = await redis_client.ping()
        redis_connected = redis_status is True
        
        if not redis_connected:
            raise HTTPException(status_code=503, detail="Redis not responding")
        
        logger.info("Health check passed")
        return HealthCheckResponse(
            status="ok",
            redis_connected=True,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

# Include routers
app.include_router(websocket_router)
app.include_router(ingestion_router)

logger.info(f"FastAPI app initialized on port {settings.BACKEND_PORT}")