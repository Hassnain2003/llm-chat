import asyncio
import json
import logging
import re
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from gateway import main
from gateway.config import Settings
from gateway.metrics import METRIC_NAMES
from gateway.queue import RequestQueue
from gateway.rate_limit import RateLimiter


@pytest.fixture(autouse=True)
def reset_gateway(monkeypatch):
    monkeypatch.setattr(main.settings, "model_backend_url", "http://backend")
    monkeypatch.setattr(main.settings, "backend_type", "ollama")
    monkeypatch.setattr(main.settings, "model_name", "tinyllama")
    monkeypatch.setattr(main.settings, "rate_limit_per_minute", 60)
    monkeypatch.setattr(main.settings, "queue_max_depth", 2)
    monkeypatch.setattr(main.settings, "request_timeout", 1)
    main._queue = RequestQueue(2)
    main._rate_limiter = RateLimiter(60, {"secret": 2})


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as async_client:
        yield async_client


def test_token_bucket_and_api_key_isolation():
    limiter = RateLimiter(1, {"key-a": 2})
    assert limiter.check("10.0.0.1", api_key="key-a")[0]
    assert limiter.check("10.0.0.1", api_key="key-a")[0]
    allowed, retry_after = limiter.check("10.0.0.1", api_key="key-a")
    assert not allowed
    assert retry_after >= 1
    assert limiter.check("10.0.0.1", api_key="key-b")[0]


def test_rate_limiter_evicts_idle_buckets():
    now = [0.0]
    limiter = RateLimiter(10, bucket_ttl=600, clock=lambda: now[0])
    limiter.check("old")
    now[0] = 601
    limiter.check("new")
    assert "ip:old" not in limiter._buckets
    assert "ip:new" in limiter._buckets


def test_rate_limiter_cap_evicts_oldest_idle_bucket():
    now = [0.0]
    limiter = RateLimiter(10, max_buckets=2, bucket_ttl=10_000, clock=lambda: now[0])
    limiter.check("first")
    now[0] = 1
    limiter.check("second")
    now[0] = 2
    limiter.check("third")
    assert len(limiter._buckets) == 2
    assert "ip:first" not in limiter._buckets


def test_rate_limiter_does_not_evict_recent_bucket_at_capacity():
    now = [0.0]
    limiter = RateLimiter(1, max_buckets=2, bucket_ttl=10_000, clock=lambda: now[0])
    limiter.check("active")
    now[0] = 1
    limiter.check("other")
    now[0] = 2
    limiter.check("active")
    limiter.check("third")
    assert "ip:active" in limiter._buckets
    assert "ip:other" not in limiter._buckets


def test_rate_limiter_works_after_idle_eviction():
    now = [0.0]
    limiter = RateLimiter(1, bucket_ttl=10, clock=lambda: now[0])
    assert limiter.check("client")[0]
    assert not limiter.check("client")[0]
    now[0] = 11
    assert limiter.check("client")[0]


@pytest.mark.asyncio
async def test_health_and_metrics(client):
    health = await client.get("/health")
    metrics = await client.get("/metrics")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert metrics.status_code == 200
    assert b"llm_chat_requests_total" in metrics.content


def test_metrics_documentation_matches_metrics_endpoint():
    readme = Path("README.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`(llm_chat_[a-z0-9_]+)`", readme))
    assert documented == set(METRIC_NAMES)
    exposition = main.metrics().body.decode()
    for metric_name in METRIC_NAMES:
        assert metric_name in exposition


def test_invalid_api_keys_config_is_rejected():
    with pytest.raises(ValueError):
        Settings(api_keys='{"broken": "not-a-limit"}')


@pytest.mark.asyncio
async def test_ready_checks_backend(client, monkeypatch):
    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            return httpx.Response(200, request=httpx.Request("GET", "http://backend/api/tags"))

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_json_formatter_includes_request_context():
    record = logging.LogRecord("gateway", logging.INFO, "", 0, "done", (), None)
    record.context = {"request_id": "req-1"}
    formatted = json.loads(main.JsonFormatter().format(record))
    assert formatted["message"] == "done"
    assert formatted["request_id"] == "req-1"


@pytest.mark.asyncio
async def test_queue_full_returns_503(client):
    main._queue.try_acquire()
    main._queue.try_acquire()
    response = await client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"


@pytest.mark.asyncio
async def test_api_key_rate_limit_returns_retry_after(client, monkeypatch):
    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", "http://backend")
            return httpx.Response(200, request=request, json={"message": {"content": "ok"}, "eval_count": 1})

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    payload = {"messages": [{"role": "user", "content": "hi"}]}
    assert (await client.post("/v1/chat/completions", headers={"X-API-Key": "secret"}, json=payload)).status_code == 200
    assert (await client.post("/v1/chat/completions", headers={"X-API-Key": "secret"}, json=payload)).status_code == 200
    limited = await client.post("/v1/chat/completions", headers={"X-API-Key": "secret"}, json=payload)
    assert limited.status_code == 429
    assert int(limited.headers["retry-after"]) >= 1


@pytest.mark.asyncio
async def test_unknown_api_key_uses_ip_fallback(client, monkeypatch):
    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            return httpx.Response(
                200,
                request=httpx.Request("POST", "http://backend"),
                json={"message": {"content": "ok"}, "eval_count": 1},
            )

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    payload = {"messages": [{"role": "user", "content": "hi"}]}
    first = await client.post("/v1/chat/completions", headers={"X-API-Key": "unknown"}, json=payload)
    second = await client.post("/v1/chat/completions", headers={"X-API-Key": "unknown"}, json=payload)
    assert first.status_code == 200
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_non_stream_ollama_adapter(client, monkeypatch):
    async def backend(*args, **kwargs):
        request = httpx.Request("POST", "http://backend/api/chat")
        return httpx.Response(200, request=request, json={"message": {"content": "hello"}, "eval_count": 3})

    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        post = backend

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    response = await client.post(
        "/v1/chat/completions",
        headers={"X-Request-ID": "req-1"},
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-1"
    assert response.json()["choices"][0]["message"]["content"] == "hello"


@pytest.mark.asyncio
async def test_non_stream_vllm_adapter(client, monkeypatch):
    monkeypatch.setattr(main.settings, "backend_type", "vllm")

    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, json):
            assert url == "http://backend/v1/chat/completions"
            assert json["max_tokens"] == 512
            response = httpx.Response(
                200,
                request=httpx.Request("POST", url),
                json={
                    "id": "chatcmpl-vllm",
                    "choices": [{"message": {"role": "assistant", "content": "hello"}}],
                    "usage": {"completion_tokens": 2},
                },
            )
            return response

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    response = await client.post(
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-vllm"


@pytest.mark.asyncio
async def test_streaming_sse_and_vllm_adapter(client, monkeypatch):
    class StreamResponse:
        def raise_for_status(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def aiter_lines(self):
            yield json.dumps({"choices": [{"delta": {"content": "hello"}}]})
            yield json.dumps({"choices": [{"delta": {"content": "world"}}]})
            yield json.dumps({"choices": [{"delta": {"content": " world"}}]})

    def stream(*args, **kwargs):
        return StreamResponse()

    monkeypatch.setattr(httpx.AsyncClient, "stream", stream)
    response = await client.post(
        "/v1/chat/completions",
        json={"stream": True, "messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 200
    assert "data: [DONE]" in response.text
    assert main._queue.depth == 0


@pytest.mark.asyncio
async def test_stream_disconnect_releases_queue_slot(monkeypatch):
    class Request:
        calls = 0

        async def is_disconnected(self):
            self.calls += 1
            return self.calls > 1

    class StreamResponse:
        def raise_for_status(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def aiter_lines(self):
            yield json.dumps({"choices": [{"delta": {"content": "hello"}}]})
            yield json.dumps({"choices": [{"delta": {"content": "world"}}]})

    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def stream(self, *args, **kwargs):
            return StreamResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    main._queue.try_acquire()
    output = [item async for item in main._stream_response(
        main.ChatRequest(messages=[main.Message(role="user", content="hi")]),
        Request(),
        "tinyllama",
        0,
    )]
    assert output == ["data: " + json.dumps({"choices": [{"delta": {"content": "hello"}}]}) + "\n\n"]
    assert main._queue.depth == 0


@pytest.mark.asyncio
async def test_stream_backend_error_releases_queue_slot(monkeypatch):
    class Request:
        async def is_disconnected(self):
            return False

    class StreamResponse:
        def raise_for_status(self):
            request = httpx.Request("POST", "http://backend")
            response = httpx.Response(502, request=request)
            raise httpx.HTTPStatusError("backend failed", request=request, response=response)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def aiter_lines(self):
            yield "never reached"

    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def stream(self, *args, **kwargs):
            return StreamResponse()

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    main._queue.try_acquire()
    output = [item async for item in main._stream_response(
        main.ChatRequest(messages=[main.Message(role="user", content="hi")]),
        Request(),
        "tinyllama",
        0,
    )]
    assert output == []
    assert main._queue.depth == 0


@pytest.mark.asyncio
async def test_timeout_returns_504_and_releases_queue(client, monkeypatch):
    async def backend(*args, **kwargs):
        raise httpx.TimeoutException("slow")

    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        post = backend

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    response = await client.post(
        "/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]}
    )
    assert response.status_code == 504
    assert main._queue.depth == 0


@pytest.mark.asyncio
async def test_queue_release_on_task_cancellation(client, monkeypatch):
    async def backend(*args, **kwargs):
        await asyncio.sleep(10)

    class BackendClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        post = backend

    monkeypatch.setattr(main.httpx, "AsyncClient", BackendClient)
    task = asyncio.create_task(
        client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    )
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert main._queue.depth == 0


@pytest.mark.asyncio
async def test_vllm_payload(monkeypatch):
    monkeypatch.setattr(main.settings, "backend_type", "vllm")
    request = main.ChatRequest(messages=[main.Message(role="user", content="hi")], stream=True)
    assert main._build_payload(request)["stream"] is True
    assert main._backend_url().endswith("/v1/chat/completions")


@pytest.mark.asyncio
async def test_request_queue_bounds():
    queue = RequestQueue(1)
    assert queue.try_acquire()
    assert not queue.try_acquire()
    queue.release()
    assert queue.try_acquire()
