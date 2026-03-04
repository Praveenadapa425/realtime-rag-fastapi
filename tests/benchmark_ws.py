import asyncio
import json
import statistics
import time
import uuid
from pathlib import Path
from typing import Dict, List

import httpx
import websockets

WS_URL = "ws://localhost:8000/query"
HTTP_URL = "http://localhost:8000"
QUERY = "Summarize the uploaded resume and list key skills"
RUNS = 5
CONCURRENT_CLIENTS = 10
INGESTION_TIMEOUT_S = 30
INGESTION_POLL_INTERVAL_S = 1.0
RESULTS_PATH = Path("tests/benchmark_results.json")


async def single_stream_metrics(query: str = QUERY) -> Dict[str, float]:
    connect_start = time.perf_counter()
    first_token_at = None
    token_count = 0
    citations_seen = 0
    response_text = []

    async with websockets.connect(WS_URL) as ws:
        await ws.send(query)
        start = time.perf_counter()

        while True:
            message = await ws.recv()
            payload = json.loads(message)
            event_type = payload.get("type")

            if event_type == "token":
                token = payload.get("payload", "")
                if token:
                    token_count += 1
                    response_text.append(token)
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                citations_seen += len(payload.get("citations", []) or [])
            elif event_type == "citation":
                citations_seen += 1
            elif event_type == "complete":
                break
            elif event_type == "error":
                raise RuntimeError(payload.get("payload", "unknown stream error"))

    end = time.perf_counter()
    ttft = (first_token_at - start) if first_token_at else (end - start)
    duration = end - start
    connect_time = start - connect_start
    tps = token_count / duration if duration > 0 else 0.0

    return {
        "server_ttft": ttft,
        "total_latency": duration,
        "connect_time": connect_time,
        "tokens": token_count,
        "tps": tps,
        "citations_seen": citations_seen,
        "response_text": "".join(response_text),
    }


async def run_serial_benchmark() -> List[Dict[str, float]]:
    results = []
    for _ in range(RUNS):
        results.append(await single_stream_metrics())
    return results


async def run_concurrency_benchmark() -> Dict[str, float]:
    start = time.perf_counter()
    results = await asyncio.gather(*[single_stream_metrics() for _ in range(CONCURRENT_CLIENTS)])
    end = time.perf_counter()

    failures = 0
    for result in results:
        if result["tokens"] <= 0:
            failures += 1

    return {
        "clients": CONCURRENT_CLIENTS,
        "success_rate": ((CONCURRENT_CLIENTS - failures) / CONCURRENT_CLIENTS) * 100,
        "wall_time": end - start,
    }


def summarize_serial(results: List[Dict[str, float]]) -> Dict[str, float]:
    ttft_values = [item["server_ttft"] for item in results]
    total_latency_values = [item["total_latency"] for item in results]
    tps_values = [item["tps"] for item in results]
    connect_times = [item["connect_time"] for item in results]

    def percentile(values: List[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        if len(ordered) == 1:
            return ordered[0]
        position = (len(ordered) - 1) * q
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction

    return {
        "server_ttft_p50_ms": percentile(ttft_values, 0.5) * 1000,
        "server_ttft_p95_ms": percentile(ttft_values, 0.95) * 1000,
        "total_latency_p50_ms": percentile(total_latency_values, 0.5) * 1000,
        "total_latency_p95_ms": percentile(total_latency_values, 0.95) * 1000,
        "tokens_per_sec_avg": statistics.mean(tps_values),
        "connect_handshake_p50_ms": percentile(connect_times, 0.5) * 1000,
        "connect_handshake_p95_ms": percentile(connect_times, 0.95) * 1000,
        "avg_citations_per_stream": statistics.mean([item["citations_seen"] for item in results]),
    }


async def measure_ingest_to_searchable_latency() -> Dict[str, float | str | bool]:
    unique_id = uuid.uuid4().hex[:8]
    filename = f"benchmark_ingest_{unique_id}.txt"
    keyword = f"GPP-UNIQUE-{unique_id}"
    document = f"This document contains a unique benchmark marker: {keyword}."

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{HTTP_URL}/ingest",
            files={"file": (filename, document.encode("utf-8"), "text/plain")},
        )
        response.raise_for_status()

    start = time.perf_counter()
    last_error = ""
    while (time.perf_counter() - start) < INGESTION_TIMEOUT_S:
        try:
            stream_result = await single_stream_metrics(
                query=f"Find the unique marker {keyword} and answer with only that marker."
            )
            if keyword in stream_result.get("response_text", ""):
                return {
                    "searchable": True,
                    "latency_s": time.perf_counter() - start,
                    "filename": filename,
                    "keyword": keyword,
                }
        except Exception as exc:
            last_error = str(exc)

        await asyncio.sleep(INGESTION_POLL_INTERVAL_S)

    return {
        "searchable": False,
        "latency_s": INGESTION_TIMEOUT_S,
        "filename": filename,
        "keyword": keyword,
        "error": last_error or "not searchable within timeout",
    }


async def main() -> None:
    await single_stream_metrics("Warmup query")
    serial_results = await run_serial_benchmark()
    serial_summary = summarize_serial(serial_results)
    concurrency_summary = await run_concurrency_benchmark()
    ingestion_summary = await measure_ingest_to_searchable_latency()

    results = {
        "serial": serial_summary,
        "concurrency": concurrency_summary,
        "ingestion_to_searchable": ingestion_summary,
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("=== Serial Streaming Benchmark ===")
    print(json.dumps(serial_summary, indent=2))
    print("=== Concurrency Benchmark ===")
    print(json.dumps(concurrency_summary, indent=2))
    print("=== Ingestion-to-Searchable Benchmark ===")
    print(json.dumps(ingestion_summary, indent=2))
    print(f"=== Results written to {RESULTS_PATH.as_posix()} ===")


if __name__ == "__main__":
    asyncio.run(main())
