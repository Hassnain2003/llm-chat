.PHONY: dev test lint loadtest loadtest-limiter loadtest-capacity loadtest-overload kind-up kind-deploy kind-down helm-lint terraform-validate

IMAGE ?= llm-chat-gateway:local
NAMESPACE ?= llm-chat

dev:
	docker compose up --build

test:
	python3 -m pytest -q --cov=gateway --cov-report=term-missing

lint:
	python3 -m ruff check gateway tests

loadtest:
	$(MAKE) loadtest-limiter
	$(MAKE) loadtest-capacity
	$(MAKE) loadtest-overload

loadtest-limiter:
	./scripts/run-loadtest-target.sh limiter

loadtest-capacity:
	./scripts/run-loadtest-target.sh capacity

loadtest-overload:
	./scripts/run-loadtest-target.sh overload

kind-up:
	kind get clusters | grep -qx llm-chat || kind create cluster --name llm-chat

kind-deploy:
	docker build -t $(IMAGE) -f gateway/Dockerfile .
	kind load docker-image $(IMAGE) --name llm-chat
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n $(NAMESPACE) -f k8s/model/configmap.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/model/deployment.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/model/service.yaml
	sed 's#llm-chat-gateway:latest#$(IMAGE)#' k8s/gateway/deployment.yaml | kubectl apply -n $(NAMESPACE) -f -
	kubectl apply -n $(NAMESPACE) -f k8s/gateway/service.yaml
	kubectl rollout status deployment/llm-chat-gateway -n $(NAMESPACE) --timeout=120s

kind-down:
	kind delete cluster --name llm-chat

helm-lint:
	helm lint ./chart -f chart/values-local.yaml

terraform-validate:
	terraform -chdir=infra init -backend=false
	terraform -chdir=infra validate
