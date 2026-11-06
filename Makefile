.PHONY: dev test lint loadtest loadtest-limiter loadtest-capacity loadtest-baseline loadtest-overload kind-up kind-deploy kind-test kind-down helm-lint terraform-validate

IMAGE ?= openai-llm-gateway:local
NAMESPACE ?= openai-llm-gateway
MODEL ?= tinyllama

dev:
	docker compose up --build

test:
	python3 -m pytest -q --cov=gateway --cov-report=term-missing

lint:
	python3 -m ruff check gateway tests

loadtest:
	$(MAKE) loadtest-limiter
	$(MAKE) loadtest-baseline
	$(MAKE) loadtest-capacity
	$(MAKE) loadtest-overload

loadtest-limiter:
	./scripts/run-loadtest-target.sh limiter

loadtest-capacity:
	./scripts/run-loadtest-target.sh capacity

loadtest-baseline:
	./scripts/run-loadtest-baseline.sh

loadtest-overload:
	./scripts/run-loadtest-target.sh overload

kind-up:
	kind get clusters | grep -qx openai-llm-gateway || kind create cluster --name openai-llm-gateway

kind-deploy:
	docker build -t $(IMAGE) -f gateway/Dockerfile .
	kind load docker-image $(IMAGE) --name openai-llm-gateway
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n $(NAMESPACE) -f k8s/model/configmap.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/model/deployment.yaml
	kubectl apply -n $(NAMESPACE) -f k8s/model/service.yaml
	sed 's#openai-llm-gateway:latest#$(IMAGE)#' k8s/gateway/deployment.yaml | kubectl apply -n $(NAMESPACE) -f -
	kubectl apply -n $(NAMESPACE) -f k8s/gateway/service.yaml
	kubectl rollout status deployment/openai-llm-gateway-model -n $(NAMESPACE) --timeout=180s
	kubectl exec -n $(NAMESPACE) deployment/openai-llm-gateway-model -- ollama pull $(MODEL)
	kubectl rollout status deployment/openai-llm-gateway-gateway -n $(NAMESPACE) --timeout=180s

kind-test:
	@set -e; \
	kubectl wait --for=condition=ready pod -l app=openai-llm-gateway-gateway -n $(NAMESPACE) --timeout=180s; \
	kubectl port-forward -n $(NAMESPACE) svc/openai-llm-gateway-gateway 18080:80 >/tmp/openai-llm-gateway-kind-port-forward.log 2>&1 & \
	pf=$$!; trap 'kill $$pf 2>/dev/null || true' EXIT; \
	sleep 3; \
	curl --fail --silent http://127.0.0.1:18080/health; \
	curl --fail --silent http://127.0.0.1:18080/ready; \
	curl --fail --silent http://127.0.0.1:18080/v1/chat/completions -H 'content-type: application/json' -d '{"model":"$(MODEL)","messages":[{"role":"user","content":"Reply with exactly: kind smoke passed"}],"max_tokens":8}' >/tmp/openai-llm-gateway-kind-completion.json; \
	curl --fail --silent -N http://127.0.0.1:18080/v1/chat/completions -H 'content-type: application/json' -d '{"model":"$(MODEL)","messages":[{"role":"user","content":"Say hello."}],"stream":true,"max_tokens":8}' >/tmp/openai-llm-gateway-kind-stream.txt; \
	grep -q 'data: \[DONE\]' /tmp/openai-llm-gateway-kind-stream.txt; \
	test "$$(kubectl get pods -n $(NAMESPACE) -l app=openai-llm-gateway-gateway -o jsonpath='{range .items[*]}{.status.containerStatuses[0].restartCount}{"\n"}{end}' | awk '$$1 != 0 {print; exit 1}')" = ""; \
	kubectl get pods -n $(NAMESPACE)

kind-deploy-mock:
	docker build -t openai-llm-gateway-mock:ci -f tests/mock_backend/Dockerfile tests/mock_backend
	kind load docker-image openai-llm-gateway-mock:ci --name openai-llm-gateway
	kind load docker-image openai-llm-gateway:local --name openai-llm-gateway
	kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -
	kubectl apply -n $(NAMESPACE) -f k8s/mock-backend.yaml
	sed 's#http://openai-llm-gateway-model:11434#http://openai-llm-gateway-mock:11434#' k8s/model/configmap.yaml | kubectl apply -n $(NAMESPACE) -f -
	sed 's#openai-llm-gateway:latest#openai-llm-gateway:local#' k8s/gateway/deployment.yaml | kubectl apply -n $(NAMESPACE) -f -
	kubectl apply -n $(NAMESPACE) -f k8s/gateway/service.yaml
	kubectl rollout status deployment/openai-llm-gateway-mock -n $(NAMESPACE) --timeout=120s
	kubectl rollout status deployment/openai-llm-gateway-gateway -n $(NAMESPACE) --timeout=120s

kind-down:
	kind delete cluster --name openai-llm-gateway

helm-lint:
	helm lint ./chart -f chart/values-local.yaml

terraform-validate:
	terraform -chdir=infra init -backend=false
	terraform -chdir=infra validate
