import logging

logger = logging.getLogger(__name__)

def chunk_text(text: str, chunk_size: int = 300) -> list:
    """
    Split text into chunks of specified size.
    
    Args:
        text: Input text to chunk
        chunk_size: Size of each chunk in characters
    
    Returns:
        List of text chunks
    """
    chunks = []
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i + chunk_size].strip()
        if chunk:  # Only add non-empty chunks
            chunks.append(chunk)
    
    logger.info(f"Split text into {len(chunks)} chunks")
    return chunks
