import asyncio
import json
import statistics
import time
from typing import Dict, List

import websockets

WS_URL = "ws://localhost:8000/query"
QUERY = "Summarize the uploaded resume and list key skills"
RUNS = 5
CONCURRENT_CLIENTS = 10


async def single_stream_metrics(query: str = QUERY) -> Dict[str, float]:
    connect_start = time.perf_counter()
    first_token_at = None
    token_count = 0

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
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
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
        "ttft": ttft,
        "duration": duration,
        "connect_time": connect_time,
        "tokens": token_count,
        "tps": tps,
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
    ttft_values = [item["ttft"] for item in results]
    tps_values = [item["tps"] for item in results]
    durations = [item["duration"] for item in results]
    connect_times = [item["connect_time"] for item in results]

    return {
        "ttft_p50_ms": statistics.median(ttft_values) * 1000,
        "ttft_p95_ms": sorted(ttft_values)[max(0, int(len(ttft_values) * 0.95) - 1)] * 1000,
        "tokens_per_sec_avg": statistics.mean(tps_values),
        "duration_avg_s": statistics.mean(durations),
        "connect_time_avg_ms": statistics.mean(connect_times) * 1000,
    }


async def main() -> None:
    await single_stream_metrics("Warmup query")
    serial_results = await run_serial_benchmark()
    serial_summary = summarize_serial(serial_results)
    concurrency_summary = await run_concurrency_benchmark()

    print("=== Serial Streaming Benchmark ===")
    print(json.dumps(serial_summary, indent=2))
    print("=== Concurrency Benchmark ===")
    print(json.dumps(concurrency_summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
