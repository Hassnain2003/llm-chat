#!/usr/bin/env python3
"""Small standard-library load-test fallback when k6 is unavailable."""

from __future__ import annotations

import json
import os
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def request(base_url: str, model: str) -> tuple[bool, float]:
    payload = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "Reply briefly."}]}
    ).encode()
    started = time.perf_counter()
    try:
        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as response:
            response.read()
        return True, time.perf_counter() - started
    except (OSError, urllib.error.URLError, TimeoutError):
        return False, time.perf_counter() - started


def run_scenario(base_url: str, model: str, users: int) -> str:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as pool:
        results = list(pool.map(lambda _: request(base_url, model), range(users)))
    elapsed = time.perf_counter() - started
    successes = sum(success for success, _ in results)
    latencies = [latency for _, latency in results]
    return (
        f"{users} users: requests={len(results)} successes={successes} "
        f"errors={len(results) - successes} throughput={len(results) / elapsed:.2f}/s "
        f"mean_latency={statistics.mean(latencies):.3f}s"
    )


def main() -> None:
    base_url = os.getenv("BASE_URL", "http://localhost:8080").rstrip("/")
    model = os.getenv("MODEL", "tinyllama")
    print(f"fallback load test: base_url={base_url} model={model}")
    for users in (10, 50, 100):
        print(run_scenario(base_url, model, users))


if __name__ == "__main__":
    main()
