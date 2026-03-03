from pydantic import BaseModel, Field
from typing import Optional

# Request/Response schemas for validation and documentation

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    redis_connected: bool
    timestamp: Optional[str] = None

class IngestionResponse(BaseModel):
    """Response after document ingestion"""
    message: str
    filename: str
    path: str

class IngestionError(BaseModel):
    """Error response for ingestion"""
    error: str
    detail: Optional[str] = None

class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str = Field(..., description="Message type: 'token', 'error', or 'complete'")
    payload: str

class QueryRequest(BaseModel):
    """Query request structure"""
    query: str = Field(..., min_length=1, max_length=1000, description="User query")
    context_limit: int = Field(default=4096, ge=512, le=8192, description="Context window size")
