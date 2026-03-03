import logging
import asyncio
from typing import AsyncGenerator, Dict, List, Any, Tuple
import json

logger = logging.getLogger(__name__)

class StreamToken:
    """Represents a token to be streamed to the client"""
    def __init__(self, token: str, token_type: str = "token", citations: List[Dict[str, Any]] = None):
        self.token = token
        self.token_type = token_type  # "token", "citation", "complete", "error"
        self.citations = citations or []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.token_type,
            "payload": self.token,
            "citations": self.citations if self.citations else None
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())

async def generate_streaming_response(
    query: str,
    context: str,
    retrieved_chunks: List[Dict[str, Any]] = None
) -> AsyncGenerator[StreamToken, None]:
    """
    Generate streaming response based on query and retrieved context.
    
    This is a MOCK generator. When you install Ollama tomorrow, swap this
    to call real LLM API instead of returning mock responses.
    
    Process:
    1. Format prompt with query + context
    2. Generate response tokens (currently mock, will be real LLM tomorrow)
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
        
        # Step 2: Generate mock response
        # NOTE: Tomorrow replace this with real Ollama call:
        # response_stream = ollama_client.generate(prompt, stream=True)
        
        mock_response = _generate_mock_response(query, context, retrieved_chunks)
        
        logger.info(f"📝 Starting token generation...")
        
        # Step 3: Stream tokens one-by-one
        async for stream_token in mock_response:
            yield stream_token
            await asyncio.sleep(0.05)  # Simulate generation delay
        
        # Step 4: Send completion signal
        logger.info(f"✅ Response generation complete")
        yield StreamToken("", token_type="complete")
    
    except Exception as e:
        logger.error(f"❌ Error generating response: {str(e)}", exc_info=True)
        yield StreamToken(f"Error: {str(e)}", token_type="error")

async def _generate_mock_response(
    query: str,
    context: str,
    retrieved_chunks: List[Dict[str, Any]]
) -> AsyncGenerator[StreamToken, None]:
    """
    Mock response generator.
    
    Simulates token-by-token generation with citations.
    Tomorrow: Replace with real Ollama API call.
    
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
    system_prompt = """You are a helpful AI assistant. Answer the following question based on the provided context. If the context doesn't contain relevant information, say so clearly. Always cite your sources."""
    
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
