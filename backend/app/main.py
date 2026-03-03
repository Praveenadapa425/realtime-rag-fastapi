import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.websocket import router as websocket_router
from app.ingestion import router as ingestion_router
from app.core.redis import redis_client
from app.schemas import HealthCheckResponse
from app.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Realtime RAG FastAPI",
    description="Real-time Retrieval Augmented Generation with streaming",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    try:
        # Test Redis connection
        await redis_client.ping()
        logger.info("✅ Redis connection successful")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    try:
        await redis_client.close()
        logger.info("✅ Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis: {str(e)}")

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
            timestamp=datetime.utcnow().isoformat()
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")

# Include routers
app.include_router(websocket_router)
app.include_router(ingestion_router)

logger.info(f"FastAPI app initialized on port {settings.BACKEND_PORT}")