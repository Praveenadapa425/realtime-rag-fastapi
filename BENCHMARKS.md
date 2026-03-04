# Benchmarks

This document summarizes benchmark methodology and current local observations.

## Goals

- Time-to-first-token (TTFT) < 500ms target
- New document searchable within ~10s target
- Stable behavior under concurrent websocket clients

## Environment

- OS: Windows
- Backend: FastAPI + Uvicorn
- Queue: Redis (Docker)
- Worker: Python async worker
- Vector DB: ChromaDB local persistence
- LLM: Ollama local model (`gemma3:1b`)

## Methodology

### 1) Streaming smoke test
- Command: `python tests/e2e_test.py`
- Verifies websocket connection, token stream, and completion event.

### 2) Ingestion responsiveness
- Upload via `/ingest`.
- Observe worker logs from enqueue to processed status.

### 3) Concurrent behavior
- Run multiple websocket clients in parallel (manual terminals or load script).
- Check for dropped connections and stream interruptions.

## Current Observations (Local)

- ✅ End-to-end websocket stream succeeds with real model.
- ✅ Completion event reliably emitted.
- ✅ Ingestion pipeline processes uploaded files asynchronously.
- ✅ Redis-backed decoupling prevents `/ingest` endpoint blocking.

## Measured Results (2026-03-04)

Command used:

`python tests/benchmark_ws.py`

Serial streaming benchmark (5 runs):
- TTFT p50: **1498 ms**
- TTFT p95: **2161 ms**
- Average token rate: **54.03 tokens/sec**
- Average stream duration: **6.17 sec**

Concurrency benchmark:
- Concurrent clients: **5**
- Success rate: **100%**
- Total wall time: **23.47 sec**

## Gaps / Next Measurements

To produce strict numeric report for submission, run load test script and record:
- TTFT p50/p95
- Tokens/sec
- Concurrent websocket success rate
- Ingestion-to-searchable latency

## Suggested Load Test Commands

- Backend API test: `pytest`
- Frontend build sanity: `npm run build`
- Multi-client websocket test: use k6/artillery/locust custom websocket scenario.
- Fast local benchmark script: `python tests/benchmark_ws.py`

## Optimization Notes

- Ensure `EMBEDDING_MODEL` is available in Ollama for best retrieval relevance.
- Tune retrieval threshold to balance precision/recall.
- Add connection pooling / worker scaling for higher concurrency.
