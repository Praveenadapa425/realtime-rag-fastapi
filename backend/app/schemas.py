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
    task_id: Optional[str] = None
    status: Optional[str] = None


class IngestionStatusResponse(BaseModel):
    """Live ingestion status for a queued task"""
    task_id: str
    filename: str
    status: str
    message: Optional[str] = None
    retries: int = 0
    updated_at: Optional[str] = None

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
