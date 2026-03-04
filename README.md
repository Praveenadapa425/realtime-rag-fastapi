# Real-Time Streaming RAG Application (FastAPI + React)

Full-stack Retrieval-Augmented Generation (RAG) app with:
- real-time token streaming over WebSocket,
- asynchronous document ingestion pipeline,
- Redis-backed background worker,
- ChromaDB vector storage,
- Ollama integration for local LLM inference.

## Features

- Streaming responses from `/query` WebSocket endpoint.
- Real-time ingestion from `/ingest` endpoint.
- Async worker pipeline: upload → chunk → embed → vector index.
- Durable Redis queue decoupling between API and worker.
- React frontend for querying, streaming output, and document uploads.

## Project Structure

```
backend/
	app/
		main.py
		ingestion.py
		websocket.py
		core/
			redis.py
			vector_db.py
		rag/
			embeddings.py
			retriever.py
			generator.py
	worker/
		worker.py
	tests/
frontend/
docker-compose.yml
submission.yml
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker + Docker Compose
- Ollama installed and running

## Environment

Canonical backend env path: `backend/.env`

```bash
cp backend/.env.example backend/.env
```

Then edit values as needed:

```
REDIS_HOST=localhost
REDIS_PORT=6379
VECTOR_DB_PATH=./chroma_data
MODEL_NAME=gemma3:1b
OLLAMA_BASE_URL=http://localhost:11434
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

For frontend, copy `frontend/.env.example` to `frontend/.env` as needed.

Optional compose-level overrides can be placed in root `.env` (Compose defaults are provided, so this is optional).

## Local Development

### 1) Start Redis

```bash
docker compose up -d redis
```

### 2) Start Backend API

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3) Start Worker

```bash
cd backend
python -m worker.worker
```

### 4) Start Frontend

```bash
cd frontend
npm install
npm run dev
```

## Docker Full Stack

```bash
docker compose up --build -d
```

Services:
- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Redis: `localhost:6379`

## API Endpoints

- `GET /health` → health + Redis connectivity status
- `POST /ingest` → upload file and enqueue ingestion
- `WS /query` → query and stream token responses

## Testing

Backend tests:

```bash
cd backend
pytest
```

End-to-end websocket smoke test:

```bash
python tests/e2e_test.py
```

Streaming benchmark with real numbers:

```bash
python tests/benchmark_ws.py
```

Latest benchmark JSON artifact:

```bash
cat tests/benchmark_results.json
```

Frontend build validation:

```bash
cd frontend
npm run build
```

## Common Issues

- **WebSocket connection refused**: backend not running on port 8000.
- **Redis connection refused**: run `docker compose up -d redis`.
- **No Ollama model found**: `ollama pull gemma3:1b`.
- **No citations in stream**: retriever threshold may filter all chunks.
- **Weak retrieval relevance**: ensure Ollama embedding endpoint/model is available.

## Notes

- Embeddings use Ollama (`EMBEDDING_MODEL`) with deterministic fallback when unavailable.
- Generator uses Ollama streaming path and emits token events.
- System is designed to evolve toward stronger retrieval and citation grounding.
