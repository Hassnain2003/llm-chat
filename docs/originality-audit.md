# Originality audit

This audit is based on this repository's git history and the round-two/round-three changes; the upstream repository was not opened or copied during this work.

- `chart/`: written for this project's `llm-chat` chart; round-two renamed resources and values and round-three marked the HPA optional and untested.
- `k8s/`: written for this project's gateway/Ollama deployment; round-three pinned the Ollama image and added a separate smoke-test mock backend.
- `infra/`: written for this project's optional EKS path; unsupported cost claims and legacy naming were removed.
- `k8s/monitoring/grafana-dashboard.json`: written for this project's `llm_chat_` metrics; round-two replaced legacy queries and round-three removed unavailable DCGM panels.
- `Makefile`: written for this project's local workflows; round-three added baseline, kind smoke, and separated load-test targets.
- `ARCHITECTURE.md`: written for this project's queue, limiter, backend, and observability decisions; autoscaling is now explicitly labeled optional and untested.
- `README.md`: written for this project's verified gateway behavior and measured tables; legacy benchmark claims were replaced with recorded runs.
- `docs/`: written for this project's benchmark evidence and screenshot checklist; no upstream prose or layout was reused.

The only retained upstream reference is the one-line acknowledgment in `README.md`: “Inspired by lmenta/inferenceforge.”
