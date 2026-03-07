import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
from app.rag.embeddings import generate_embedding
from app.core.vector_db import get_collection

logger = logging.getLogger(__name__)

class RetrievalResult:
    """Represents a retrieved document chunk with metadata"""
    def __init__(self, chunk: str, source: str, chunk_id: int, similarity_score: float, metadata: Dict[str, Any]):
        self.chunk = chunk
        self.source = source
        self.chunk_id = chunk_id
        self.similarity_score = similarity_score
        self.metadata = metadata
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk": self.chunk,
            "source": self.source,
            "chunk_id": self.chunk_id,
            "similarity_score": round(self.similarity_score, 3),
            "metadata": self.metadata
        }

async def retrieve_context(
    query: str,
    top_k: int = 3,
    relevance_threshold: float = 0.3
) -> tuple[List[RetrievalResult], str]:
    """
    Retrieve relevant document chunks from ChromaDB based on query.
    
    Process:
    1. Generate embedding for the query
    2. Search ChromaDB for similar chunks
    3. Filter by relevance threshold
    4. Return top-K results with metadata
    
    Args:
        query: User query string
        top_k: Number of top results to return (default: 3)
        relevance_threshold: Minimum similarity score (0-1, default: 0.3)
    
    Returns:
        Tuple of (results list, formatted context string)
    """
    try:
        logger.info(f"🔍 Retrieving context for query: {query[:50]}...")
        
        # Step 1: Generate embedding for query
        query_embedding = await generate_embedding(query)
        logger.debug(f"Generated query embedding (dim: {len(query_embedding)})")
        
        # Step 2: Search ChromaDB (use larger candidate pool, then rerank)
        candidate_count = min(max(top_k * 8, 20), 100)
        collection = get_collection()
        search_results = await asyncio.to_thread(
            collection.query,
            query_embeddings=[query_embedding],
            n_results=candidate_count,
            include=["documents", "metadatas", "distances"],
        )
        
        logger.info(f"📚 Found {len(search_results['documents'][0])} potential matches")
        
        # Step 3: Process results
        retrieval_results = []
        
        if search_results['documents'] and search_results['documents'][0]:
            all_candidates = []
            query_terms = set(re.findall(r"[a-zA-Z0-9]+", query.lower()))
            query_compact = " ".join(query.lower().split())

            for i, (doc, metadata, distance) in enumerate(zip(
                search_results['documents'][0],
                search_results['metadatas'][0],
                search_results['distances'][0]
            )):
                # Convert distance to similarity score (0-1)
                # Chromadb returns euclidean distance, convert to similarity
                similarity_score = 1 / (1 + distance)

                doc_lower = (doc or "").lower()
                doc_terms = set(re.findall(r"[a-zA-Z0-9]+", doc_lower))
                lexical_overlap = (
                    len(query_terms.intersection(doc_terms)) / max(len(query_terms), 1)
                    if query_terms
                    else 0.0
                )
                phrase_bonus = 0.2 if query_compact and query_compact in doc_lower else 0.0
                rerank_score = similarity_score + (0.35 * lexical_overlap) + phrase_bonus
                
                candidate = RetrievalResult(
                    chunk=doc,
                    source=metadata.get("source", "unknown"),
                    chunk_id=metadata.get("chunk", i),
                    similarity_score=rerank_score,
                    metadata={
                        **metadata,
                        "vector_similarity": round(similarity_score, 6),
                        "lexical_overlap": round(lexical_overlap, 6),
                        "phrase_bonus": round(phrase_bonus, 6),
                    },
                )
                all_candidates.append(candidate)

            all_candidates.sort(key=lambda c: c.similarity_score, reverse=True)

            for i, candidate in enumerate(all_candidates[: max(top_k * 2, top_k)]):
                score = candidate.similarity_score
                if score >= relevance_threshold:
                    retrieval_results.append(candidate)
                    logger.info(f"  ✓ Chunk {i}: {candidate.source} (score: {score:.3f})")
                else:
                    logger.info(f"  ✗ Chunk {i}: Below threshold (score: {score:.3f})")

                if len(retrieval_results) >= top_k:
                    break

            if not retrieval_results and all_candidates:
                fallback_count = min(top_k, len(all_candidates))
                retrieval_results = all_candidates[:fallback_count]
                logger.warning(
                    "No chunks met relevance threshold %.2f; returning top %d fallback chunks",
                    relevance_threshold,
                    fallback_count,
                )
        
        # Step 4: Format context for LLM
        context_str = _format_context_for_llm(retrieval_results)
        
        logger.info(f"✅ Retrieved {len(retrieval_results)} relevant chunks")
        
        return retrieval_results, context_str
    
    except Exception as e:
        logger.error(f"❌ Error retrieving context: {str(e)}", exc_info=True)
        return [], ""

def _format_context_for_llm(results: List[RetrievalResult]) -> str:
    """
    Format retrieved chunks into a string for the LLM prompt.
    
    Format:
    Source: document.txt (chunk 0, score: 0.95)
    Content: ...
    ---
    
    Args:
        results: List of RetrievalResult objects
    
    Returns:
        Formatted context string
    """
    if not results:
        return "No relevant documents found in knowledge base."
    
    context_parts = []
    
    for result in results:
        section = f"""Source: {result.source} (chunk {result.chunk_id}, relevance: {result.similarity_score:.1%})
Content:
{result.chunk}
---"""
        context_parts.append(section)
    
    return "\n".join(context_parts)

async def retrieve_with_stats(
    query: str,
    top_k: int = 3
) -> Dict[str, Any]:
    """
    Retrieve context and return detailed statistics.
    
    Useful for debugging and monitoring retrieval performance.
    
    Args:
        query: User query
        top_k: Number of results to retrieve
    
    Returns:
        Dictionary with results and statistics
    """
    try:
        results, context = await retrieve_context(query, top_k)
        
        stats = {
            "query": query,
            "results_count": len(results),
            "results": [r.to_dict() for r in results],
            "context": context,
            "avg_score": sum(r.similarity_score for r in results) / len(results) if results else 0
        }
        
        logger.info(f"Retrieval stats: {len(results)} results, avg score: {stats['avg_score']:.3f}")
        
        return stats
    
    except Exception as e:
        logger.error(f"Error in retrieve_with_stats: {str(e)}", exc_info=True)
        return {
            "query": query,
            "results_count": 0,
            "results": [],
            "context": "",
            "error": str(e)
        }
