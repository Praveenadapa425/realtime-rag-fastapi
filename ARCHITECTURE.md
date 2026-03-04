# Architecture

## High-Level Diagram

```text
┌──────────────────────────┐
│        Frontend          │
│   React + Vite (UI)      │
└─────────────┬────────────┘
	      │ HTTP/WS
┌─────────────▼────────────┐
│      FastAPI Backend     │
│ /health /ingest /query   │
└───────┬─────────┬────────┘
	│         │
	│Redis List Queue (`RPUSH`)  │Vector Search / LLM Context
┌───────▼───┐   ┌─▼────────────────────┐
│   Redis   │   │      ChromaDB        │
│ ingestion │   │ vector collection     │
└───────┬───┘   └──────────┬───────────┘
	│                  │
┌───────▼──────────────────▼───────────┐
│         Worker Process                │
│ `BLPOP` → read file → chunk → embed → upsert │
└────────────────────────────────────────┘
	      │
	      ▼
       Ollama (Local LLM)
```

## Components

### 1. Frontend
- Sends file upload requests to `/ingest`.
- Opens WebSocket to `/query` for token streaming.
- Renders tokens incrementally and displays citations.

### 2. Backend API (FastAPI)
- `GET /health`: checks service and Redis connectivity.
- `POST /ingest`: validates file and enqueues ingestion message in Redis.
- `WS /query`: retrieves context, calls generator, streams token events.

### 3. Redis
- Acts as durable message queue (Redis List key `ingestion_queue`).
- Decouples API request handling from ingestion work.
- Stores processed idempotency keys and a dead-letter queue (`ingestion_dead_letter`).

### 4. Worker
- Blocks on Redis queue (`BLPOP`) and consumes tasks reliably.
- Processes uploaded files asynchronously.
- Chunks text and stores vectors + metadata in ChromaDB.
- Retries failed tasks and dead-letters after max attempts.

### 5. ChromaDB
- Stores embeddings and metadata in persistent collection.
- Used for similarity retrieval at query time.

### 6. Ollama
- Streams model response tokens from local model.
- Backend relays stream to client in WebSocket message format.

## WebSocket Message Contract

```json
{"type":"token","payload":"..."}
{"type":"citation","payload":{"source":"...","chunk_id":0,"similarity":0.9,"sentence":"..."}}
{"type":"error","payload":{"code":"...","message":"..."}}
{"type":"complete","payload":""}
```

## Design Decisions

- Async-first backend for low latency and concurrency.
- Worker decoupling to avoid blocking `/ingest` requests.
- Local vector DB for simple reproducible setup.
- Local LLM via Ollama for cost-free development.
