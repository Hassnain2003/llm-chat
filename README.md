# LLM Chat API

> **Production-ready LLM inference gateway on Kubernetes.** OpenAI-compatible chat API with request queuing, per-IP rate limiting, Prometheus metrics, Helm deployment, and CPU/GPU switching — deploy on a laptop or AWS EKS with a single flag.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Kubernetes](https://img.shields.io/badge/Kubernetes-1.24+-green.svg)
![Helm](https://img.shields.io/badge/Helm-3.0+-orange.svg)
![Terraform](https://img.shields.io/badge/Terraform-1.5+-red.svg)

---

## What this project provides

Most "deploy an LLM" guides end at `ollama run` or a bare Docker container. **LLM Chat API** adds the production layer on top:

- A FastAPI gateway that exposes an OpenAI-compatible `/v1/chat/completions` endpoint
- Per-IP request rate limiting (sliding window, configurable)
- asyncio.Semaphore-backed request queue with configurable depth
- Prometheus metrics: request rate, latency (p50/p95/p99), queue depth, token throughput, active requests, backend errors
- A Grafana dashboard with 12 panels for operational visibility
- A Helm chart that swaps between local CPU and cloud GPU by changing a single values file
- Raw Kubernetes manifests for users who prefer kubectl apply over Helm
- Terraform infrastructure for EKS, GPU node groups, and Karpenter provisioning

Everything is self-contained in one repository — no shared libraries, no monolithic setup guides.

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
curl http://localhost:8080/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"gemma3:1b","messages":[{"role":"user","content":"Say hello in one sentence."}]}'
```

---

## Deploying to Kubernetes

### Option A: Helm (recommended)

```bash
helm install llm-chat ./chart -f chart/values-gpu.yaml
helm install llm-chat ./chart -f chart/values-local.yaml
```

### Option B: Raw manifests

```bash
kubectl create namespace llm-chat
kubectl apply -n llm-chat -f k8s/model/configmap.yaml
kubectl apply -n llm-chat -f k8s/model/deployment.yaml
kubectl apply -n llm-chat -f k8s/model/service.yaml
kubectl apply -n llm-chat -f k8s/gateway/deployment.yaml
kubectl apply -n llm-chat -f k8s/gateway/service.yaml
kubectl apply -n llm-chat -f k8s/gateway/hpa.yaml
```

---

## How it works

```
Client                  Gateway (FastAPI)                  Model Backend
──────────────          ────────────────────────────         ───────────────
  │                                         │                    │
  ├─ POST /v1/chat/completions ───────────► │                    │
  │                                         ├─ Rate limiter     │
  │                                         │   (60 req/min/IP) │
  │                                         ├─ Request queue    │
  │                                         │   (asyncio.Semaphore) │
  │                                         └────────────────────┤
  │                                                         ▼
  │                                            Model processes
  │                                            (Ollama or vLLM)
  │                                                         │
  │                                           Response in
  │                                           OpenAI format
  │                                                         │
  │◄── Streaming or non-streaming JSON response ────────────│
```

### Why two services?

The **gateway** is stateless, horizontally scalable, and CPU-cheap. The **model backend** holds model weights in GPU memory — expensive to scale, slow to start. Decoupling them lets you add gateway replicas for traffic spikes without touching the GPU.

### One-flag switch: local → GPU

The entire difference between running on your laptop and running on a T4 is two YAML files. No code changes, no branches.

```bash
# Local — CPU, free, runs in Docker
helm install llm-chat ./chart -f chart/values.yaml

# AWS EKS — NVIDIA T4 spot (~$0.15/hr)
helm install llm-chat ./chart -f chart/values-gpu.yaml
```

| Setting | Local | GPU (EKS) |
|---------|-------|-----------|
| model.backend | ollama | vllm |
| model.name | gemma3:1b | mistralai/Mistral-7B-Instruct-v0.2 |
| model.backendPort | 11434 | 8000 |
| gpu.enabled | false | true |
| gateway.replicas | 1 | 2 |
| autoscaling.enabled | false | true |

---

## Kubernetes GPU scheduling

Three things must be true for a pod to land on a GPU node:

1. NVIDIA Device Plugin DaemonSet — runs on every GPU node, registers nvidia.com/gpu as a schedulable resource.
2. Taint + Toleration — GPU nodes are tainted nvidia.com/gpu=true:NoSchedule.
3. Resource request — the model container requests nvidia.com/gpu: 1.

---

## Autoscaling

The HPA scales the **gateway**, not the model backend (GPU cold start is too slow for reactive scaling). Two metrics drive scaling simultaneously:

- CPU utilisation — triggers when gateways are compute-bound
- llm_chat_queue_depth — custom Prometheus metric via prometheus-adapter

Queue-depth scaling fires earlier and more predictably than CPU alone. A slow model will fill the queue before it stresses the gateway's CPU.

The model backend uses Karpenter to watch for unschedulable pods, provision a new node, and land the pod within 2-3 minutes. GPU nodes cost money — you only want them when needed.

---

## Monitoring

Prometheus scrapes the gateway at :9090/metrics. Key metrics:

| Metric | Type | Purpose |
|--------|------|---------|
| llm_chat_requests_total | Counter | Request rate and error rate |
| llm_chat_request_duration_seconds | Histogram | Latency SLOs p50/p95/p99 |
| llm_chat_queue_depth | Gauge | HPA trigger + capacity planning |
| llm_chat_tokens_total | Counter | Throughput and cost estimation |
| llm_chat_active_requests | Gauge | Concurrency — saturated early |
| llm_chat_backend_errors_total | Counter | Backend health by error type |

Grafana dashboard: k8s/monitoring/grafana-dashboard.json (12 panels).

---

## Repository layout

```
.
├── README.md
├── ARCHITECTURE.md
├── LICENSE
├── requirements.txt
├── Makefile
├── .gitignore
│
├── gateway/
│   ├── main.py           Routes, queue, rate limiter, adapters
│   ├── config.py         pydantic-settings configuration
│   ├── metrics.py        Prometheus metrics
│   ├── queue.py          Async request queue
│   └── Dockerfile        Container image build
│
├── chart/                 Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── values-local.yaml # CPU-only local configuration
│   ├── values-gpu.yaml   # AWS EKS GPU configuration
│   └── templates/        Helm templates
│       ├── configmap.yaml
│       ├── gateway/      deployment, service, HPA
│       └── model/        deployment, service
│
├── k8s/                   Raw Kubernetes manifests
│   ├── gateway/           deployment.yaml, service.yaml, hpa.yaml
│   ├── model/             configmap.yaml, deployment.yaml, service.yaml
│   ├── monitoring/        ServiceMonitor + Grafana dashboard JSON
│   └── nvidia-device-plugin.yaml
│
├── infra/                 Terraform
│   ├── main.tf
│   └── variables.tf
│
└── tests/                 Test suite (empty contributors welcome)
```

---

## Prerequisites

- Docker (for local runs)
- Kubernetes 1.24+ (for deployment)
- Helm 3.0+ (for Helm-based deployment)
- Terraform 1.5+ (for cloud infrastructure)
- NVIDIA GPU + Device Plugin (for GPU deployment)

---

## Getting started

### Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn gateway.main:app --reload
```

### Kubernetes (Helm)

```bash
helm install llm-chat ./chart
```

### Kubernetes (raw manifests)

```bash
kubectl apply -f k8s/model/configmap.yaml
kubectl apply -f k8s/model/deployment.yaml
kubectl apply -f k8s/model/service.yaml
kubectl apply -f k8s/gateway/deployment.yaml
kubectl apply -f k8s/gateway/service.yaml
```

### Terraform / cloud

```bash
terraform init
terraform plan -var="region=us-east-1"
terraform apply
```

---

## License

MIT © 2026 — Hassnain2003

---

## Contributing

Contributions welcome! This is a fresh project and there is plenty of room for improvement:

- Add integration tests (tests/)
- Add OpenAPI/Swagger docs
- Add CI/CD pipeline
- Add more model adapters (LM Studio, TGI, etc.)
- Improve Grafana dashboard panels
- Add e2e deployment scripts

Please open an issue or submit a pull request.
