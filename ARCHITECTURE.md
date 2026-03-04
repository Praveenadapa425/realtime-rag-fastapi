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
	│Pub/Sub  │Vector Search / LLM Context
┌───────▼───┐   ┌─▼────────────────────┐
│   Redis   │   │      ChromaDB        │
│ ingestion │   │ vector collection     │
└───────┬───┘   └──────────┬───────────┘
	│                  │
┌───────▼──────────────────▼───────────┐
│         Worker Process                │
│ read file → chunk → embed → upsert    │
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
- Acts as lightweight message queue (Pub/Sub channel `ingestion_queue`).
- Decouples API request handling from ingestion work.

### 4. Worker
- Listens to Redis channel.
- Processes uploaded files asynchronously.
- Chunks text and stores vectors + metadata in ChromaDB.

### 5. ChromaDB
- Stores embeddings and metadata in persistent collection.
- Used for similarity retrieval at query time.

### 6. Ollama
- Streams model response tokens from local model.
- Backend relays stream to client in WebSocket message format.

## WebSocket Message Contract

```json
{"type":"token","payload":"...","citations":[...]}
{"type":"error","payload":"..."}
{"type":"complete","payload":""}
```

## Design Decisions

- Async-first backend for low latency and concurrency.
- Worker decoupling to avoid blocking `/ingest` requests.
- Local vector DB for simple reproducible setup.
- Local LLM via Ollama for cost-free development.
