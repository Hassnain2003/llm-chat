#!/usr/bin/env python3
"""Render one measured load-test section into docs/results.md."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

RESULTS = Path("docs/results.md")
START = "<!-- LOADTEST:{target}:START -->"
END = "<!-- LOADTEST:{target}:END -->"


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def metadata() -> list[str]:
    cpu = command("lscpu", "-p=MODELNAME") if Path("/usr/bin/lscpu").exists() else "unknown"
    cpu = next((line for line in cpu.splitlines() if line and not line.startswith("#")), "unknown")
    cores = command("getconf", "_NPROCESSORS_ONLN")
    memory = command("free", "-h").splitlines()[1].split()[1]
    commit = command("git", "rev-parse", "HEAD")
    return [
        f"- Hardware: {cpu}, {cores} cores, {memory} RAM, no GPU",
        "- Model: tinyllama, Q4_0, 1.1B",
        f"- Date (UTC): {command('date', '-u', '+%Y-%m-%dT%H:%M:%SZ')}",
        f"- Git commit: `{commit}`",
    ]


def gateway_histogram() -> tuple[int, str, str]:
    text = urllib.request.urlopen("http://localhost:8080/metrics", timeout=10).read().decode()
    buckets: list[tuple[float, int]] = []
    for line in text.splitlines():
        if not line.startswith("llm_chat_time_to_first_chunk_seconds_bucket"):
            continue
        match = re.search(r'le="([^"]+)"[^ ]* ([0-9]+(?:\.[0-9]+)?)$', line)
        if match:
            upper = float("inf") if match.group(1) == "+Inf" else float(match.group(1))
            buckets.append((upper, int(float(match.group(2)))))
    buckets.sort()
    total = buckets[-1][1] if buckets else 0

    def quantile(q: float) -> str:
        if not buckets or not total:
            return "n/a"
        target = total * q
        for upper, count in buckets:
            if count >= target:
                return "inf" if upper == float("inf") else f"{upper:g}s"
        return "n/a"

    return total, quantile(0.5), quantile(0.95)


def section(target: str, data: dict) -> str:
    lines = [START.format(target=target), f"## {target.title()} load test", *metadata()]
    lines.append(f"- Exact command: `make loadtest-{target}`")
    if target == "limiter":
        lines += [
            "",
            "Limiter verification, not a performance benchmark.",
            "",
            "| 200 responses | 429 responses | 429 without Retry-After | key-b 200 responses |",
            "|---:|---:|---:|---:|",
            f"| {data['status200']} | {data['status429']} | {data['retryAfterMissing']} | {data['keyBSuccess']} |",
        ]
    elif target == "overload":
        max_depth = sys.argv[3] if len(sys.argv) > 3 else "not recorded"
        lines += [
            "",
            "| 200 responses | 503 responses | Other statuses | 503 without Retry-After | Maximum observed queue depth |",
            "|---:|---:|---:|---:|---:|",
            f"| {data['status200']} | {data['status503']} | {data['statusOther']} | {data['retryAfterMissing']} | {max_depth} |",
        ]
    else:
        lines += [
            "",
            "Capacity results include only 2xx responses in latency and token-rate columns.",
            "",
            "| VUs | Successful req/s | Completion tokens/s | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) | 200 | 429 | 503 | Other |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for vus, values in data["stages"].items():
            latency = values["latency"]
            duration = 60
            lines.append(
                f"| {vus} | {values['successful'] / duration:.3f} | {values['completionTokens'] / duration:.3f} | "
                f"{latency.get('med', 'n/a')} | {latency.get('p(95)', 'n/a')} | "
                f"{latency.get('p(99)', 'n/a')} | {values['successful']} | "
                f"{values['status429']} | {values['status503']} | {values['statusOther']} |"
            )
        histogram_count, histogram_p50, histogram_p95 = gateway_histogram()
        lines += [
            "",
            "Streaming stage (4 VUs, 60s): `llm_chat_time_to_first_chunk_seconds` histogram values were collected from the gateway scrape after the run.",
            (
                f"- Successful streams: {data['stream']['successful']}; other statuses: "
                f"{data['stream']['other']}; gateway histogram count: {histogram_count}; "
                f"p50: {histogram_p50}; p95: {histogram_p95}."
            ),
        ]
    lines.append(END.format(target=target))
    return "\n".join(lines)


def replace(target: str, rendered: str) -> None:
    existing = RESULTS.read_text() if RESULTS.exists() else "# Load-test results\n"
    start = START.format(target=target)
    end = END.format(target=target)
    before = existing.split(start, 1)[0].rstrip()
    after = existing.split(end, 1)[1] if end in existing else ""
    RESULTS.write_text(f"{before}\n\n{rendered}\n{after.lstrip()}")


if __name__ == "__main__":
    target, result_path = sys.argv[1], sys.argv[2]
    replace(target, section(target, json.loads(Path(result_path).read_text())))
