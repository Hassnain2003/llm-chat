# LLM Inference Forge

> **Production-grade LLM inference platform on Kubernetes.** OpenAI-compatible API, request queuing, Prometheus metrics, and a Helm chart that switches between CPU (free, local) and GPU (AWS EKS) with two values.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.24+-green.svg)
![Helm](https://img.shields.io/badge/Helm-3.0+-orange.svg)
![Terraform](https://img.shields.io/badge/Terraform-1.5+-red.svg)

---

## What it does

Most "deploy an LLM" tutorials stop at `ollama run` or a single Docker container. LLM Inference Forge builds the production layer on top: the queue, the rate limiter, the metrics, the Helm chart, and the GPU node configuration.


---

## Quick start (local, no Kubernetes)

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com)

```bash
# 1. Start Ollama and pull a model
ollama serve &
ollama pull gemma3:1b

# 2. Install gateway dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Start the gateway
MODEL_BACKEND_URL=http://localhost:11434 \
MODEL_NAME=gemma3:1b \
BACKEND_TYPE=ollama \
RATE_LIMIT_PER_MINUTE=120 \
QUEUE_MAX_DEPTH=100 \
uvicorn gateway.main:app --host 0.0.0.0 --port 8080
```

Test it:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gemma3:1b","messages":[{"role":"user","content":"Say hello in one sentence."}]}'
```

---

## Kubernetes deployment

```bash
# Install the Helm chart
helm repo add llm-inference-forge https://your-org.github.io/llm-inference-forge
helm install llm-inference-forge llm-inference-forge/llm-inference-forge -f values-gpu.yaml

# Or use the raw manifests
kubectl create namespace llm-inference-forge
kubectl apply -n llm-inference-forge -f k8s/model/configmap.yaml
kubectl apply -n llm-inference-forge -f k8s/model/deployment.yaml
kubectl apply -n llm-inference-forge -f k8s/model/service.yaml
kubectl apply -n llm-inference-forge -f k8s/gateway/deployment.yaml
kubectl apply -n llm-inference-forge -f k8s/gateway/service.yaml
kubectl apply -n llm-inference-forge -f k8s/gateway/hpa.yaml
```

---

## Kubernetes GPU scheduling

Three things must be in place for a pod to land on a GPU node:

```yaml
# 1. Tolerate the GPU taint — prevents CPU workloads from landing on GPU nodes
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule

# 2. Pin to GPU node type
nodeSelector:
  node.kubernetes.io/instance-type: g4dn.xlarge

# 3. Request the GPU — K8s finds a free slot and exclusively assigns it
resources:
  limits:
    nvidia.com/gpu: "1"
```

The NVIDIA Device Plugin DaemonSet (deployed via `make nvidia-plugin`) runs on every GPU node and registers `nvidia.com/gpu` as a schedulable resource. Without it, Kubernetes doesn't know GPUs exist.

---

## Autoscaling

The HPA scales the **gateway**, not the model backend (GPU cold start is too slow for reactive scaling).

Two metrics drive scaling simultaneously:
- **CPU utilisation** — standard K8s metric
- **`llm-inference-forge_queue_depth`** — custom Prometheus metric via prometheus-adapter

Scaling on queue depth fires earlier and more predictably than CPU alone. A slow model fills the queue before it stresses the gateway's CPU.

The model backend uses Karpenter: when a GPU pod can't be scheduled (no node exists), Karpenter provisions one. Slower than HPA (~2–3 min), but GPU nodes are expensive — you only want them when actually needed.

---

## Prometheus metrics

| Metric | Type | Description |
|--------|------|-------------|
| `llm-inference-forge_requests_total` | Counter | Request count by model and status |
| `llm-inference-forge_request_duration_seconds` | Histogram | Latency p50/p95/p99 |
| `llm-inference-forge_queue_depth` | Gauge | Waiting requests — also drives the HPA |
| `llm-inference-forge_tokens_total` | Counter | Tokens generated (throughput + cost estimation) |
| `llm-inference-forge_active_requests` | Gauge | Concurrent in-flight requests |
| `llm-inference-forge_backend_errors_total` | Counter | Backend failures by error type |

Latency buckets are non-uniform (0.1s → 60s) because LLM inference is slow and unpredictable. A 5s bucket tells you more than a 1s bucket for this workload.

Import `k8s/monitoring/grafana-dashboard.json` to get the full 12-panel dashboard.

---

## Project structure

```
llm-inference-forge/
├── gateway/
│   ├── main.py          # FastAPI app — queue, rate limiter, OpenAI adapter
│   ├── queue.py         # asyncio.Semaphore-based request queue
│   ├── metrics.py       # Prometheus metric definitions
│   ├── config.py        # Settings (pydantic-settings)
│   └── Dockerfile
├── chart/               # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-local.yaml
│   ├── values-gpu.yaml
│   └── templates/
│       ├── configmap.yaml
│       ├── gateway/     # deployment, service, hpa
│       └── model/       # deployment, service
├── k8s/                 # Raw Kubernetes manifests
│   ├── gateway/
│   ├── model/
│   ├── monitoring/      # Prometheus ServiceMonitor + Grafana dashboard
│   └── nvidia-device-plugin.yaml
├── infra/               # Terraform — EKS + GPU node group + Karpenter
│   ├── main.tf
│   └── variables.tf
├── requirements.txt
└── ARCHITECTURE.md
```

---

## See also

[ARCHITECTURE.md](ARCHITECTURE.md) — detailed design rationale: why the gateway and model backend are separate, how request flow works, autoscaling strategy, and the metrics design.

## License

MIT © 2026 [Your GitHub Organization] — [Your Name / Team Name]



```
                         ┌──────────────────────────────────┐
 Client (OpenAI SDK)  ──► │      Gateway (FastAPI)          │
                          │                                  │
                          │  ┌──────────────────────────┐   │
                          │  │  Rate limiter            │   │
                          │  │  60 req/min per IP       │   │
                          │  └─────────────┬────────────┘   │
                          │                │                 │
                          │  ┌─────────────▼────────────┐   │
                          │  │  Request queue           │   │
                          │  │  asyncio.Semaphore       │   │
                          │  └─────────────┬────────────┘   │
                          │                │                 │
                          │  ┌─────────────▼────────────┐   │
                          │  │  Prometheus metrics      │   │
                          │  │  /metrics endpoint       │   │
                          │  └──────────────────────────┘   │
                          └────────────────┬─────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │       Model Backend               │
                          │                                   │
                          │  Local:  Ollama (CPU)             │
                          │  AWS:    vLLM (NVIDIA T4)         │
                          └───────────────────────────────────┘
                                           │
                          ┌────────────────▼─────────────────┐
                          │   Prometheus → Grafana            │
                          │   12 panels: latency, throughput, │
                          │   queue depth, GPU utilisation    │
                          └───────────────────────────────────┘
```

---

## One-flag switch: local → GPU

The entire difference between running on a MacBook and running on a T4 GPU is two values files:

```bash
# Local — CPU, free, runs in Docker
helm install llm-inference-forge ./chart -f chart/values-local.yaml

# AWS EKS — NVIDIA T4 spot (~$0.15/hr)
helm install llm-inference-forge ./chart -f chart/values-gpu.yaml
```

| Setting | Local | GPU (EKS) |
|---------|-------|-----------|
| `model.backend` | ollama | vllm |
| `model.name` | gemma3:1b | mistralai/Mistral-7B |
| `gpu.enabled` | false | true |
| `gateway.replicas` | 1 | 2 |
| `autoscaling.enabled` | false | true |

Same gateway image. Same manifests. Same Prometheus config.
