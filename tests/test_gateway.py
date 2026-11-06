import asyncio
import json

import httpx
import pytest
import pytest_asyncio

from gateway import main
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


@pytest.mark.asyncio
async def test_health_and_metrics(client):
    health = await client.get("/health")
    metrics = await client.get("/metrics")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert metrics.status_code == 200
    assert b"inferenceforge_requests_total" in metrics.content


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
