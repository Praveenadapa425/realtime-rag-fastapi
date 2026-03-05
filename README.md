# 🚀 Real-Time Streaming RAG Application

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-FFD700?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNGRkQiIHN0cm9rZS13aWR0aD0iMiI+PGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTAiLz48L3N2Zz4=&logoColor=black)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNGRkYiIHN0cm9rZS13aWR0aD0iMiI+PHBhdGggZD0iTTEyIDJMMiA3bDEwIDUgMTAtNS0xMC01ek0yIDE3bDEwIDUgMTAtNU0yIDEybDEwIDUgMTAtNSIvPjwvc3ZnPg==&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-010101?style=for-the-badge&logo=socketdotio&logoColor=white)

**Full-stack Retrieval-Augmented Generation with real-time token streaming**

[Architecture](ARCHITECTURE.md) · [Benchmarks](BENCHMARKS.md) · [Documentation](docs/)

</div>

---

## 📋 Overview

This project implements a production-ready **Retrieval-Augmented Generation (RAG)** system featuring:

- ⚡ **Real-time token streaming** over WebSocket for instant responses
- 🔀 **Asynchronous document ingestion** pipeline with background workers
- 🗄️ **Redis-backed message queue** for reliable task distribution
- 📊 **ChromaDB vector storage** for efficient similarity search
- 🤖 **Ollama integration** for local LLM inference (cost-free development)
- 🎨 **Modern React frontend** with live query interface

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🌊 **Streaming Responses** | Token-by-token streaming via `/query` WebSocket endpoint |
| 📥 **Real-time Ingestion** | Non-blocking file upload through `/ingest` endpoint |
| 🔧 **Async Worker Pipeline** | Upload → Chunk → Embed → Vector Index workflow |
| 🛢️ **Redis Queue** | Durable message queue decoupling API from workers |
| 💻 **Interactive UI** | React-based frontend for queries and document management |
| 🔄 **Idempotency** | Prevents duplicate processing with Redis keys |
| 📈 **Scalable Design** | Async-first architecture for high concurrency |

---

## 🏗️ Project Structure

```
realtime-rag-fastapi/
├── backend/
│   ├── app/
│   │   ├── core/          # Core modules (Redis, VectorDB)
│   │   ├── rag/           # RAG components (Embeddings, Retriever, Generator)
│   │   ├── main.py        # FastAPI application & endpoints
│   │   ├── ingestion.py   # Document ingestion logic
│   │   ├── websocket.py   # WebSocket handlers
│   │   ├── schemas.py     # Pydantic models
│   │   └── config.py      # Configuration management
│   ├── worker/
│   │   └── worker.py      # Background worker process
│   ├── tests/             # Backend test suite
│   ├── uploads/           # Uploaded documents
│   └── chroma_data/       # Vector database storage
├── frontend/
│   ├── src/               # React components
│   ├── dist/              # Production build
│   └── package.json       # Frontend dependencies
├── tests/                 # E2E and benchmark tests
├── docs/                  # Documentation
├── docker-compose.yml     # Container orchestration
└── .env.example           # Environment template
```

---

## 📦 Prerequisites

Ensure you have the following installed before running the application:

| Software | Version | Link |
|----------|---------|------|
| **Python** | 3.12+ | [Download](https://www.python.org/downloads/) |
| **Node.js** | 20+ | [Download](https://nodejs.org/) |
| **Docker** | Latest | [Get Docker](https://www.docker.com/get-started/) |
| **Ollama** | Latest | [Install Ollama](https://ollama.ai/) |

> **Note**: Ollama must be running locally before starting the backend.

---

## ⚙️ Environment Configuration

### Backend Setup

1. **Copy environment file:**
```bash
cp backend/.env.example backend/.env
```

2. **Configure backend variables** (`backend/.env`):
```ini
# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379

# Vector Database
VECTOR_DB_PATH=./chroma_data

# Model Configuration
MODEL_NAME=gemma3:1b
OLLAMA_BASE_URL=http://localhost:11434

# Service URLs
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:3000
BACKEND_URL=http://localhost:8000
```

### Frontend Setup

```bash
cp frontend/.env.example frontend/.env
```

### Optional: Docker Compose Overrides

Create a `.env` file in the root directory for compose-level environment variable overrides.

---

## 🚀 Quick Start

### Option 1: Local Development

#### Step 1: Start Redis
```bash
docker compose up -d redis
```

#### Step 2: Start Backend API
```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Step 3: Start Worker Process
```bash
cd backend
python -m worker.worker
```

#### Step 4: Start Frontend
```bash
cd frontend
npm install
npm run dev
```

**Access Points:**
- 🌐 Frontend: `http://localhost:3000`
- 🔌 Backend API: `http://localhost:8000`
- 📊 API Docs: `http://localhost:8000/docs`

---

### Option 2: Docker Full Stack

```bash
docker compose up --build -d
```

**Services:**
| Service | URL | Port |
|---------|-----|------|
| Frontend | `http://localhost:3000` | 3000 |
| Backend API | `http://localhost:8000` | 8000 |
| Redis | `localhost:6379` | 6379 |

To stop all services:
```bash
docker compose down
```

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check + Redis connectivity status |
| `POST` | `/ingest` | Upload file and enqueue for processing |
| `WS` | `/query` | Query with real-time token streaming |

### Example Usage

**Health Check:**
```bash
curl http://localhost:8000/health
```

**File Ingestion:**
```bash
curl -X POST -F "file=@document.pdf" http://localhost:8000/ingest
```

**WebSocket Query:**
```javascript
const ws = new WebSocket('ws://localhost:8000/query');
ws.send(JSON.stringify({ question: 'What is RAG?' }));
```

---

## 🧪 Testing & Benchmarking

### Unit Tests
```bash
cd backend
pytest
```

### End-to-End Test
```bash
python tests/e2e_test.py
```

### Streaming Performance Benchmark
```bash
python tests/benchmark_ws.py
```

View benchmark results:
```bash
cat tests/benchmark_results.json
```

### Frontend Build Validation
```bash
cd frontend
npm run build
```

---

## 🔍 Architecture Overview

For detailed architecture diagrams and component flow, see [ARCHITECTURE.md](ARCHITECTURE.md)

```
┌─────────────┐         ┌──────────────┐         ┌──────────┐
│  Frontend   │ ──────▶ │   Backend    │ ──────▶ │  Redis   │
│ React + Vite│  HTTP   │   FastAPI    │   Queue │  Queue   │
└─────────────┘         └──────────────┘         └──────────┘
       ▲                       │                        │
       │         WebSocket     │                        ▼
       │ ◀─────────────────────┘                ┌──────────────┐
       │           Token Stream                 │    Worker    │
       │                                        └──────────────┘
       │                                                │
       │         ┌──────────────┐                      │
       └────────▶│    Ollama    │ ◀────────────────────┘
                 │     LLM      │         ChromaDB
                 └──────────────┘         ┌──────────────┐
                                          │  Vector DB   │
                                          └──────────────┘
```

---

## 📝 Technical Notes

- **Embeddings**: Generated using Ollama with deterministic fallback when unavailable
- **Generator**: Streams tokens via Ollama and emits token events in real-time
- **Scalability**: Designed for horizontal scaling with Redis queue decoupling
- **Evolution**: System architected to support advanced retrieval and citation grounding

---

<div align="center">

**Built with ❤️ using FastAPI, React, and Modern AI Technologies**

For questions or contributions, please refer to the project repository.

</div>
