"""OpenAI-compatible inference gateway with bounded concurrency and observability."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from starlette.responses import Response

from gateway.config import settings
from gateway.metrics import (
    active_requests,
    backend_errors,
    cancelled_requests,
    request_count,
    request_latency,
    stream_chunks_per_second,
    time_to_first_chunk,
    tokens_generated,
)
from gateway.queue import RequestQueue
from gateway.rate_limit import RateLimiter

_queue: RequestQueue
_rate_limiter: RateLimiter


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "message": record.getMessage(),
                **getattr(record, "context", {}),
            }
        )


logger = logging.getLogger("gateway")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _queue, _rate_limiter
    _queue = RequestQueue(max_depth=settings.queue_max_depth)
    _rate_limiter = RateLimiter(
        settings.rate_limit_per_minute,
        settings.api_key_limits,
        bucket_ttl=settings.rate_limit_bucket_ttl_seconds,
        max_buckets=settings.rate_limit_max_buckets,
    )
    yield


app = FastAPI(
    title="OpenAI LLM Gateway",
    description="OpenAI-compatible gateway for Ollama and a vLLM adapter tested with a mocked backend",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    started_at = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_complete",
        extra={
            "context": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            }
        },
    )
    return response


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[Message]
    stream: bool = False
    max_tokens: int | None = None
    temperature: float | None = 0.7


def _api_key(request: Request) -> str | None:
    value = request.headers.get("X-API-Key")
    if value:
        return value
    authorization = request.headers.get("Authorization", "")
    return authorization.removeprefix("Bearer ").strip() or None


def _build_ollama_payload(req: ChatRequest) -> dict:
    return {
        "model": req.model or settings.model_name,
        "messages": [message.model_dump() for message in req.messages],
        "stream": req.stream,
        "options": {
            "temperature": req.temperature if req.temperature is not None else 0.7,
            **({"num_predict": req.max_tokens} if req.max_tokens else {}),
        },
    }


def _build_vllm_payload(req: ChatRequest) -> dict:
    return {
        "model": req.model or settings.model_name,
        "messages": [message.model_dump() for message in req.messages],
        "stream": req.stream,
        "max_tokens": req.max_tokens or 512,
        "temperature": req.temperature if req.temperature is not None else 0.7,
    }


def _backend_url() -> str:
    suffix = "/v1/chat/completions" if settings.backend_type == "vllm" else "/api/chat"
    return f"{settings.model_backend_url.rstrip('/')}{suffix}"


def _build_payload(req: ChatRequest) -> dict:
    return _build_vllm_payload(req) if settings.backend_type == "vllm" else _build_ollama_payload(req)


def _record_cancel(reason: str, model_name: str) -> None:
    cancelled_requests.labels(reason=reason, model=model_name).inc()
    request_count.labels(status=reason, model=model_name).inc()


async def _watch_disconnect(request: Request) -> None:
    while True:
        if await request.is_disconnected():
            return
        await asyncio.sleep(0.05)


async def _request_backend(req: ChatRequest, request: Request) -> dict:
    async with httpx.AsyncClient(timeout=settings.request_timeout) as client:
        backend_task = asyncio.create_task(client.post(_backend_url(), json=_build_payload(req)))
        disconnect_task = asyncio.create_task(_watch_disconnect(request))
        done, pending = await asyncio.wait(
            {backend_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        if disconnect_task in done and backend_task not in done:
            backend_task.cancel()
            raise asyncio.CancelledError
        response = await backend_task
        response.raise_for_status()
        return response.json()


@app.get("/health")
def health():
    return {"status": "ok", "backend": settings.backend_type, "model": settings.model_name}


@app.get("/ready")
async def ready():
    url = (
        f"{settings.model_backend_url.rstrip('/')}/api/tags"
        if settings.backend_type == "ollama"
        else f"{settings.model_backend_url.rstrip('/')}/health"
    )
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Backend not ready") from exc
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/queue/status")
def queue_status():
    return {"depth": _queue.depth, "max_depth": settings.queue_max_depth, "full": _queue.is_full()}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest, request: Request):
    model_name = req.model or settings.model_name
    client_ip = request.client.host if request.client else "unknown"
    allowed, retry_after = _rate_limiter.check(client_ip, api_key=_api_key(request))
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
    if not _queue.try_acquire():
        raise HTTPException(
            status_code=503,
            detail="Queue full - try again shortly",
            headers={"Retry-After": "1"},
        )

    active_requests.inc()
    started_at = time.perf_counter()
    if req.stream:
        return StreamingResponse(
            _stream_response(req, request, model_name, started_at),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Request-ID": request.state.request_id},
        )

    try:
        data = await _non_stream_response(req, request, model_name, started_at)
        return data
    except asyncio.CancelledError:
        _record_cancel("cancelled", model_name)
        raise
    except httpx.TimeoutException as exc:
        _record_cancel("timeout", model_name)
        raise HTTPException(status_code=504, detail="Backend request timed out") from exc
    except httpx.HTTPError as exc:
        backend_errors.labels(error_type=type(exc).__name__).inc()
        request_count.labels(status="error", model=model_name).inc()
        raise HTTPException(status_code=502, detail="Backend error") from exc
    finally:
        active_requests.dec()
        _queue.release()


async def _non_stream_response(
    req: ChatRequest, request: Request, model_name: str, started_at: float
) -> dict:
    data = await _request_backend(req, request)
    elapsed = time.perf_counter() - started_at
    request_latency.labels(model=model_name).observe(elapsed)
    request_count.labels(status="success", model=model_name).inc()
    if settings.backend_type == "ollama":
        completion_tokens = data.get("eval_count", 0)
        content = data.get("message", {}).get("content", "")
        tokens_generated.labels(model=model_name).inc(completion_tokens)
        return {
            "id": f"chatcmpl-{request.state.request_id}",
            "object": "chat.completion",
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"completion_tokens": completion_tokens},
        }
    completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
    tokens_generated.labels(model=model_name).inc(completion_tokens)
    return data


async def _stream_response(
    req: ChatRequest, request: Request, model_name: str, started_at: float
) -> AsyncIterator[str]:
    chunk_count = 0
    backend_token_count: int | None = None
    first_token_at: float | None = None
    status = "success"
    try:
        timeout = httpx.Timeout(settings.request_timeout)
        async with httpx.AsyncClient(timeout=timeout) as client, client.stream(
            "POST", _backend_url(), json=_build_payload(req)
        ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if await request.is_disconnected():
                        _record_cancel("cancelled", model_name)
                        status = "cancelled"
                        return
                    if not line:
                        continue
                    now = time.perf_counter()
                    if first_token_at is None:
                        first_token_at = now
                        time_to_first_chunk.labels(model=model_name).observe(now - started_at)
                    chunk_count += 1
                    try:
                        chunk_data = json.loads(line.removeprefix("data: ").strip())
                    except json.JSONDecodeError:
                        chunk_data = {}
                    usage = chunk_data.get("usage", {})
                    if isinstance(usage, dict) and isinstance(usage.get("completion_tokens"), int):
                        backend_token_count = usage["completion_tokens"]
                    if isinstance(chunk_data.get("eval_count"), int):
                        backend_token_count = chunk_data["eval_count"]
                    yield f"data: {line}\n\n"
    except asyncio.CancelledError:
        _record_cancel("cancelled", model_name)
        status = "cancelled"
        raise
    except httpx.TimeoutException:
        _record_cancel("timeout", model_name)
        status = "timeout"
        raise
    except httpx.HTTPError as exc:
        backend_errors.labels(error_type=type(exc).__name__).inc()
        status = "error"
        request_count.labels(status=status, model=model_name).inc()
        return
    finally:
        elapsed = time.perf_counter() - started_at
        request_latency.labels(model=model_name).observe(elapsed)
        if backend_token_count is not None:
            tokens_generated.labels(model=model_name).inc(backend_token_count)
        if chunk_count:
            stream_chunks_per_second.labels(model=model_name).set(chunk_count / max(elapsed, 0.001))
        if status == "success":
            request_count.labels(status=status, model=model_name).inc()
        active_requests.dec()
        _queue.release()
    yield "data: [DONE]\n\n"
