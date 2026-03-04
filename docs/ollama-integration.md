# Ollama Integration Guide

This project now uses Ollama for both:
- response generation (`MODEL_NAME` via `/api/generate`), and
- embeddings (`EMBEDDING_MODEL` via `/api/embeddings`).

## Required Environment Variables

Set these in your backend environment (`backend/.env`):

- `OLLAMA_BASE_URL=http://localhost:11434`
- `MODEL_NAME=gemma3:1b` (or any local chat model)
- `EMBEDDING_MODEL=nomic-embed-text` (or any local embedding model)

## Pull Required Models

```bash
ollama pull gemma3:1b
ollama pull nomic-embed-text
```

## Verify Ollama Is Running

```bash
ollama --version
ollama list
```

## How It Works in This Codebase

- Generation path: `backend/app/rag/generator.py`
  - Calls `POST /api/generate` with `stream=true`
  - Streams tokens over WebSocket as they arrive

- Embedding path: `backend/app/rag/embeddings.py`
  - Calls `POST /api/embeddings`
  - Returns vector for both query and document chunks
  - Includes deterministic fallback embedding if Ollama/model is unavailable

## Troubleshooting

- If generation fails:
  - Confirm `MODEL_NAME` exists in `ollama list`
  - Confirm `OLLAMA_BASE_URL` points to running Ollama

- If embeddings fail:
  - Confirm `EMBEDDING_MODEL` exists in `ollama list`
  - If unavailable, app uses deterministic fallback embeddings (retrieval quality will be lower)

- Docker note:
  - Compose uses `http://host.docker.internal:11434` so containers can reach host Ollama on Windows/macOS.
