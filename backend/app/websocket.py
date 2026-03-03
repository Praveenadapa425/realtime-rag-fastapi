import logging
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/query")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming query responses
    - Accepts user queries
    - Streams token-by-token responses
    - Handles disconnections gracefully
    """
    client_id = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    
    try:
        await websocket.accept()
        logger.info(f"✅ WebSocket client connected: {client_id}")
        
        while True:
            # Receive query from client
            try:
                query = await websocket.receive_text()
                logger.info(f"📨 Query received from {client_id}: {query[:50]}...")
                
                if not query.strip():
                    await websocket.send_json({
                        "type": "error",
                        "payload": "Query cannot be empty"
                    })
                    continue
                
                # Mock streaming response (placeholder for RAG integration)
                words = ["This", "is", "a", "streaming", "response", "from", "the", "RAG", "system"]
                
                for word in words:
                    try:
                        await websocket.send_json({
                            "type": "token",
                            "payload": word + " "
                        })
                        await asyncio.sleep(0.1)  # Simulate processing delay
                    except Exception as e:
                        logger.error(f"Error sending token: {str(e)}")
                        break
                
                # Send completion signal
                await websocket.send_json({
                    "type": "complete",
                    "payload": ""
                })
                logger.info(f"✅ Response streaming completed for {client_id}")
                
            except WebSocketDisconnect:
                logger.warning(f"📭 WebSocket client disconnected: {client_id}")
                break
            except Exception as e:
                logger.error(f"Error processing query from {client_id}: {str(e)}", exc_info=True)
                try:
                    await websocket.send_json({
                        "type": "error",
                        "payload": f"Processing error: {str(e)}"
                    })
                except:
                    break
    
    except Exception as e:
        logger.error(f"WebSocket endpoint error for {client_id}: {str(e)}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except:
            pass