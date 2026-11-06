#!/usr/bin/env python3
"""Render baseline-versus-gateway comparisons from recorded Markdown tables."""

from __future__ import annotations

import re
from pathlib import Path

RESULTS = Path("docs/results.md")
START = "<!-- BASELINE-COMPARISON:START -->"
END = "<!-- BASELINE-COMPARISON:END -->"
METRICS = (
    ("Successful req/s", 1),
    ("Completion tokens/s", 2),
    ("p50 latency (ms)", 3),
    ("p95 latency (ms)", 4),
    ("p99 latency (ms)", 5),
)


def rows(kind: str, label: str) -> dict[str, list[float]]:
    match = re.search(
        rf"## {kind} load test \({re.escape(label)}\)(.*?)(?=<!-- LOADTEST:)",
        RESULTS.read_text(),
        re.DOTALL,
    )
    if not match:
        raise SystemExit(f"missing recorded section: {label}")
    values: dict[str, list[float]] = {}
    for row in re.findall(r"^\| ([1248]|16) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|", match.group(1), re.MULTILINE):
        values[row[0]] = [float(item.strip()) for item in row[1:]]
    return values


def table(run: str) -> list[str]:
    gateway = rows("Capacity", f"run-{run}")
    baseline = rows("Baseline", f"run-{run}")
    lines = [
        f"### Run {run}: gateway versus direct Ollama",
        "",
        "Sources: recorded `capacity-run-%s` and `baseline-run-%s` sections above; both were "
        "2xx-only and include their own UTC date, command, and git commit." % (run, run),
        "",
        "| VUs | Metric | Gateway | Baseline | Absolute difference | Difference (%) |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for vus in ("1", "4"):
        for metric, index in METRICS:
            gateway_value = gateway[vus][index - 1]
            baseline_value = baseline[vus][index - 1]
            difference = gateway_value - baseline_value
            percentage = difference / baseline_value * 100 if baseline_value else 0
            lines.append(
                f"| {vus} | {metric} | {gateway_value:.3f} | {baseline_value:.3f} | "
                f"{difference:.3f} | {percentage:.2f}% |"
            )
    return lines


def render() -> str:
    return "\n".join(
        [
            START,
            "## Baseline comparison",
            "",
            "The direct baseline uses Ollama native `/api/chat`; the gateway uses "
            "`/v1/chat/completions`. Differences represent gateway overhead plus noise, "
            "not a pure gateway-only measurement. Each side was run twice.",
            "",
            *table("1"),
            "",
            *table("2"),
            END,
        ]
    )


existing = RESULTS.read_text()
if START in existing and END in existing:
    before, remainder = existing.split(START, 1)
    _, after = remainder.split(END, 1)
    existing = before.rstrip() + "\n\n" + render() + after
else:
    existing = existing.rstrip() + "\n\n" + render() + "\n"
RESULTS.write_text(existing)
