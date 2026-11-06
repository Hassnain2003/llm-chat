# Architecture

## Components

- **Gateway**: FastAPI process that validates the OpenAI-compatible request, applies rate limits, reserves bounded capacity, translates backend payloads, and exposes metrics.
- **Model backend**: Ollama for local CPU development or a vLLM adapter tested with a mocked backend for an optional GPU deployment.
- **Observability**: Prometheus scrapes `/metrics`; Grafana reads Prometheus and displays the checked-in dashboard definition.

Runtime configuration uses the environment variables `MODEL_BACKEND_URL`, `MODEL_NAME`,
`BACKEND_TYPE`, `RATE_LIMIT_PER_MINUTE`, `API_KEYS`, `QUEUE_MAX_DEPTH`, and
`REQUEST_TIMEOUT`. The same names are wired by the Compose stack, Helm gateway template,
and raw Kubernetes gateway deployment.

## Design decisions

### Why a bounded queue?

Model inference is an expensive, finite resource. The gateway reserves one process-local slot before calling the backend and releases it in a `finally` path, including cancellation and timeout. Returning `503` when capacity is full is explicit backpressure rather than unbounded memory growth.

### Optional HPA design (not verified here)

CPU utilization alone can miss a saturated model backend: the gateway may be mostly waiting on I/O while requests accumulate. The repository includes an optional HPA manifest that names `llm_chat_queue_depth`, but this project has not verified Prometheus Adapter, the custom-metrics API, or scale-up behavior in kind.

### Why gateway and model are separate services?

The gateway is stateless with respect to model weights and can be updated or replicated independently. The model service owns the large, slow-to-load model process and can be scheduled on CPU or GPU nodes without coupling the API deployment to a particular accelerator.

### Why token buckets?

Token buckets allow a configured burst up to the bucket capacity while refilling at a predictable requests-per-minute rate. API-key buckets are isolated from one another; requests without a configured key use an IP bucket. Idle buckets are removed after 10 minutes by default, and the limiter caps the number of buckets at 10,000; both limits are configurable. These limits are per gateway replica, not shared across replicas.

## Known limitations

- Rate-limit buckets, queue depth, and active-request metrics are process-local. A multi-replica deployment needs a shared limiter and carefully aggregated capacity if global enforcement is required.
- Client disconnect detection is cooperative and depends on the ASGI server reporting disconnects.
- The backend adapters normalize common Ollama responses and pass through vLLM responses; the vLLM adapter is tested with a mocked backend and is not a full provider compatibility layer.
- Kubernetes, Terraform, and GPU settings require environment-specific security, storage, ingress, and secret review.
