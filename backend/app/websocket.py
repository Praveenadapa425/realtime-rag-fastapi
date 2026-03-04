import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/query")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint wired into full RAG pipeline.

    1. Accepts query text from client.
    2. Runs retrieval against vector DB.
    3. Streams generator tokens + citations back.
    4. Handles errors mid-stream gracefully.
    """
    client_id = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    
    try:
        await websocket.accept()
        logger.info(f"✅ WebSocket client connected: {client_id}")

        while True:
            terminal_sent = False

            async def send_terminal_event(event_type: str, payload):
                nonlocal terminal_sent
                if terminal_sent:
                    return
                await websocket.send_json({"type": event_type, "payload": payload})
                terminal_sent = True

            try:
                query = await websocket.receive_text()
                logger.info(f"📨 Query from {client_id}: {query[:50]}...")

                if not query.strip():
                    await send_terminal_event(
                        "error",
                        {"code": "INVALID_QUERY", "message": "Query cannot be empty"},
                    )
                    continue

                await websocket.send_json({"type": "token", "payload": "Analyzing your documents... "})

                # retrieve context and metadata
                from app.rag.retriever import retrieve_context
                from app.rag.generator import generate_streaming_response

                results, context = await retrieve_context(query)
                logger.info(f"🔍 Retrieved {len(results)} chunks for query")

                # stream generator output
                async for stream_token in generate_streaming_response(query, context, [r.to_dict() for r in results]):
                    try:
                        stream_data = stream_token.to_dict()
                        stream_type = stream_data.get("type")

                        if stream_type in {"complete", "error"}:
                            await send_terminal_event(stream_type, stream_data.get("payload"))
                            break

                        await websocket.send_json(stream_data)
                    except Exception as exc:
                        logger.error(f"Error sending token during stream: {str(exc)}")
                        break

                if not terminal_sent:
                    await send_terminal_event("complete", "")

                # after generator sends complete token we break loop or continue next query
                logger.info(f"✅ Finished streaming for {client_id}")

            except WebSocketDisconnect:
                logger.warning(f"📭 Client disconnected: {client_id}")
                break
            except Exception as e:
                logger.error(f"Error in RAG pipeline for {client_id}: {str(e)}", exc_info=True)
                try:
                    await send_terminal_event(
                        "error",
                        {"code": "RAG_PIPELINE_ERROR", "message": str(e)},
                    )
                except:
                    break

    except Exception as e:
        logger.error(f"WebSocket init error for {client_id}: {str(e)}", exc_info=True)
        try:
            await websocket.close(code=1011, reason="WS_INIT_ERROR")
        except:
            pass