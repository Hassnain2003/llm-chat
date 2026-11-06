"""Prometheus metrics for the inference gateway."""

from prometheus_client import Counter, Gauge, Histogram

request_count = Counter(
    "inferenceforge_requests_total",
    "Total inference requests",
    ["status", "model"],
)

request_latency = Histogram(
    "inferenceforge_request_duration_seconds",
    "End-to-end request latency",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

queue_depth = Gauge(
    "inferenceforge_queue_depth",
    "Current number of requests waiting in queue",
)

tokens_generated = Counter(
    "inferenceforge_tokens_total",
    "Total tokens generated",
    ["model"],
)

active_requests = Gauge(
    "inferenceforge_active_requests",
    "Requests currently being processed",
)

backend_errors = Counter(
    "inferenceforge_backend_errors_total",
    "Errors from model backend",
    ["error_type"],
)

time_to_first_token = Histogram(
    "inferenceforge_time_to_first_token_seconds",
    "Time from request start until the first streamed token",
    ["model"],
)

stream_tokens_per_second = Gauge(
    "inferenceforge_stream_tokens_per_second",
    "Most recently observed streaming token rate",
    ["model"],
)

cancelled_requests = Counter(
    "inferenceforge_cancelled_requests_total",
    "Requests cancelled by the client or timed out",
    ["reason", "model"],
)
