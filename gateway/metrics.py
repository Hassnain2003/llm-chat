"""Prometheus metrics for the inference gateway."""

from prometheus_client import Counter, Gauge, Histogram

METRIC_NAMES = (
    "llm_chat_requests_total",
    "llm_chat_request_duration_seconds",
    "llm_chat_queue_depth",
    "llm_chat_tokens_total",
    "llm_chat_active_requests",
    "llm_chat_backend_errors_total",
    "llm_chat_time_to_first_chunk_seconds",
    "llm_chat_stream_chunks_per_second",
    "llm_chat_cancelled_requests_total",
)

request_count = Counter(
    "llm_chat_requests_total",
    "Total inference requests",
    ["status", "model"],
)

request_latency = Histogram(
    "llm_chat_request_duration_seconds",
    "End-to-end request latency",
    ["model"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

queue_depth = Gauge(
    "llm_chat_queue_depth",
    "Current number of requests waiting in queue",
)

tokens_generated = Counter(
    "llm_chat_tokens_total",
    "Total tokens generated",
    ["model"],
)

active_requests = Gauge(
    "llm_chat_active_requests",
    "Requests currently being processed",
)

backend_errors = Counter(
    "llm_chat_backend_errors_total",
    "Errors from model backend",
    ["error_type"],
)

time_to_first_chunk = Histogram(
    "llm_chat_time_to_first_chunk_seconds",
    "Time from request start until the first streamed token",
    ["model"],
)

stream_chunks_per_second = Gauge(
    "llm_chat_stream_chunks_per_second",
    "Most recently observed streaming chunk rate",
    ["model"],
)

cancelled_requests = Counter(
    "llm_chat_cancelled_requests_total",
    "Requests cancelled by the client or timed out",
    ["reason", "model"],
)
