import logging
import asyncio
import re
from typing import AsyncGenerator, Dict, List, Any, Tuple
import json
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

class StreamToken:
    """Represents a token to be streamed to the client"""
    def __init__(
        self,
        token: Any,
        token_type: str = "token",
        citations: List[Dict[str, Any]] = None,
        metadata: Dict[str, Any] = None,
    ):
        self.token = token
        self.token_type = token_type  # "token", "citation", "complete", "error"
        self.citations = citations or []
        self.metadata = metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        response = {
            "type": self.token_type,
            "payload": self.token,
        }
        if self.citations:
            response["citations"] = self.citations
        if self.metadata:
            response["metadata"] = self.metadata
        return response
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def _select_best_citation(sentence: str, retrieved_chunks: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    if not sentence.strip() or not retrieved_chunks:
        return None

    sentence_terms = set(re.findall(r"[a-zA-Z0-9]+", sentence.lower()))
    if not sentence_terms:
        return None

    best_chunk = None
    best_overlap = -1

    for chunk in retrieved_chunks:
        chunk_text = str(chunk.get("chunk", ""))
        chunk_terms = set(re.findall(r"[a-zA-Z0-9]+", chunk_text.lower()))
        overlap = len(sentence_terms.intersection(chunk_terms))
        if overlap > best_overlap:
            best_overlap = overlap
            best_chunk = chunk

    if not best_chunk:
        return None

    return {
        "source": best_chunk.get("source", "document"),
        "chunk_id": best_chunk.get("chunk_id", 0),
        "similarity": best_chunk.get("similarity_score", 0.0),
        "sentence": sentence.strip(),
        "method": "sentence_overlap",
    }


async def warmup_ollama() -> None:
    """Warm up generation model to reduce cold-start latency."""
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": settings.MODEL_NAME,
        "prompt": "Warmup",
        "stream": False,
        "options": {"num_predict": 1},
        "keep_alive": "30m",
    }

    timeout = httpx.Timeout(connect=5.0, read=20.0, write=20.0, pool=20.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("✅ Ollama warmup completed")
    except Exception as exc:
        logger.warning("Ollama warmup skipped: %s", str(exc))

async def generate_streaming_response(
    query: str,
    context: str,
    retrieved_chunks: List[Dict[str, Any]] = None
) -> AsyncGenerator[StreamToken, None]:
    """
    Generate streaming response based on query and retrieved context.
    
    Streams response from Ollama using /api/generate.
    
    Process:
    1. Format prompt with query + context
    2. Generate response tokens via Ollama streaming API
    3. Track which chunks are cited
    4. Stream tokens one-by-one to client
    5. Include citation info with relevant tokens
    
    Args:
        query: User query string
        context: Formatted context from retriever
        retrieved_chunks: List of retrieved chunks with metadata
    
    Yields:
        StreamToken objects (token, citation, complete, error)
    """
    try:
        logger.info(f"🤖 Generating response for query: {query[:50]}...")
        
        if retrieved_chunks is None:
            retrieved_chunks = []
        
        # Step 1: Build RAG prompt
        prompt = _build_rag_prompt(query, context)
        logger.debug(f"Built prompt with {len(prompt)} characters")
        
        # Step 2: Generate Ollama streamed response
        ollama_response = _generate_ollama_response(prompt, retrieved_chunks)
        
        logger.info(f"📝 Starting token generation...")
        
        # Step 3: Stream tokens and explicit citation events
        terminal_emitted = False
        async for stream_token in ollama_response:
            if stream_token.token_type in {"complete", "error"}:
                terminal_emitted = True
            yield stream_token
            await asyncio.sleep(0.001)
        
        # Step 4: Send completion signal
        if not terminal_emitted:
            logger.info(f"✅ Response generation complete")
            yield StreamToken("", token_type="complete")
    
    except Exception as e:
        logger.error(f"❌ Error generating response: {str(e)}", exc_info=True)
        yield StreamToken(
            {
                "code": "GENERATION_ERROR",
                "message": str(e),
            },
            token_type="error",
        )

async def _generate_mock_response(
    query: str,
    context: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> AsyncGenerator[StreamToken, None]:
    """
    Mock response generator.

    Legacy fallback/testing utility.
    
    Args:
        query: User query
        context: Retrieved context
        retrieved_chunks: Metadata about retrieved chunks
    
    Yields:
        StreamToken objects
    """
    # Mock response based on query
    if "rag" in query.lower():
        response_tokens = [
            "RAG", " stands", " for", " Retrieval", "-", "Augmented", " Generation",
            ",", " a", " technique", " that", " combines", " information", " retrieval",
            " with", " language", " model", " generation", ".", " It", " retrieves",
            " relevant", " documents", " and", " uses", " them", " as", " context",
            " for", " generating", " more", " accurate", " responses", "."
        ]
    else:
        response_tokens = [
            "Based", " on", " the", " knowledge", " base", ",", " I", " can",
            " provide", " information", " about", " your", " query", ".", " The",
            " retrieved", " documents", " suggest", " that", " this", " is", " an",
            " important", " topic", " worth", " exploring", " further", "."
        ]
    
    # Yield tokens with citations
    token_count = 0
    for i, token in enumerate(response_tokens):
        citations = []
        
        # Add citation every 5 tokens
        if i > 0 and i % 5 == 0 and retrieved_chunks:
            chunk = retrieved_chunks[0]
            citations.append({
                "source": chunk.get("source", "document"),
                "chunk_id": chunk.get("chunk_id", 0),
                "similarity": chunk.get("similarity_score", 0.0)
            })
        
        stream_token = StreamToken(token, token_type="token", citations=citations)
        yield stream_token
        token_count += 1
        
        logger.debug(f"Yielded token {token_count}: {token}")

async def _generate_ollama_response(
    prompt: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> AsyncGenerator[StreamToken, None]:
    """
    Stream tokens from local Ollama server.

    Endpoint: POST /api/generate with stream=true
    """
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": settings.MODEL_NAME,
        "prompt": prompt,
        "stream": True
    }

    timeout = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=30.0)

    try:
        attempts = 2
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("POST", url, json=payload) as response:
                        response.raise_for_status()

                        token_index = 0
                        current_sentence = ""
                        async for line in response.aiter_lines():
                            if not line:
                                continue

                            try:
                                data = json.loads(line)
                            except json.JSONDecodeError:
                                logger.debug("Skipping non-JSON Ollama stream line")
                                continue

                            if data.get("done"):
                                break

                            token = data.get("response", "")
                            if not token:
                                continue

                            citation_payload = None
                            current_sentence += token
                            if any(end in token for end in [".", "!", "?"]):
                                citation_payload = _select_best_citation(current_sentence, retrieved_chunks)
                                current_sentence = ""

                            yield StreamToken(token, token_type="token")

                            if citation_payload:
                                yield StreamToken(
                                    citation_payload,
                                    token_type="citation",
                                    citations=[citation_payload],
                                )
                            token_index += 1
                return
            except httpx.ConnectError:
                if attempt >= attempts:
                    raise
                await asyncio.sleep(1.0)

    except httpx.HTTPStatusError as exc:
        logger.error(f"Ollama HTTP error: {exc.response.status_code} - {exc.response.text}")
        yield StreamToken(
            {
                "code": "OLLAMA_HTTP_ERROR",
                "message": "Ollama request failed. Check model name and server status.",
                "status_code": exc.response.status_code,
            },
            token_type="error",
        )
    except Exception as exc:
        logger.error(f"Ollama stream error: {str(exc)}", exc_info=True)
        yield StreamToken(
            {
                "code": "OLLAMA_UNAVAILABLE",
                "message": f"Unable to reach Ollama at {settings.OLLAMA_BASE_URL}. Ensure Ollama is running and reachable from backend.",
            },
            token_type="error",
        )

def _build_rag_prompt(query: str, context: str) -> str:
    """
    Build RAG prompt for LLM.
    
    Format:
    You are a helpful AI assistant. Answer the following question based on
    the provided context. If the context doesn't contain relevant information,
    say so.
    
    Context:
    [CONTEXT]
    
    Question: [QUERY]
    
    Answer:
    
    Args:
        query: User query
        context: Retrieved context from ChromaDB
    
    Returns:
        Formatted prompt
    """
    system_prompt = """You are a helpful AI assistant. Answer using only the provided context. Keep answers concise and factual. If context is missing, clearly say so. Cite source/chunk at sentence boundaries when possible."""
    
    prompt = f"""{system_prompt}

Context:
{context}

Question: {query}

Answer:"""
    
    return prompt

async def generate_with_citations(
    query: str,
    context: str,
    retrieved_chunks: List[Dict[str, Any]] = None
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Generate complete response and collect all citations.
    
    Useful for non-streaming scenarios.
    
    Args:
        query: User query
        context: Retrieved context
        retrieved_chunks: Retrieved chunks list
    
    Returns:
        Tuple of (full response text, citations list)
    """
    try:
        full_response = ""
        all_citations = []
        
        async for stream_token in generate_streaming_response(query, context, retrieved_chunks):
            if stream_token.token_type == "token":
                full_response += stream_token.token
                all_citations.extend(stream_token.citations)
        
        return full_response, all_citations
    
    except Exception as e:
        logger.error(f"Error in generate_with_citations: {str(e)}", exc_info=True)
        return "", []

def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    
    Uses simple heuristic: ~4 characters per token on average.
    
    Args:
        text: Input text
    
    Returns:
        Estimated token count
    """
    # Simple estimation: ~4 characters per token
    estimate = len(text) / 4
    return max(1, int(estimate))
