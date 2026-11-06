#!/usr/bin/env bash
set -euo pipefail

label="${RUN_LABEL:-latest}"
result_file="/tmp/openai-llm-gateway-baseline-${label}-summary.json"
rm -f "$result_file"
docker compose up --build -d ollama
trap 'docker compose down --remove-orphans' EXIT
until curl --fail --silent http://localhost:11434/api/tags >/dev/null; do sleep 2; done
docker compose exec -T ollama ollama pull "${MODEL:-tinyllama}" >/dev/null
RESULT_FILE="$result_file" MODEL="${MODEL:-tinyllama}" k6 run --quiet loadtest/baseline.js
python3 scripts/render-loadtest-result.py baseline "$result_file" "" "$label"
