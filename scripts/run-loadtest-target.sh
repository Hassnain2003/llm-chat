#!/usr/bin/env bash
set -euo pipefail

target="${1:?target required: limiter, capacity, or overload}"
case "$target" in
  limiter) compose_env=(LOADTEST_RATE_LIMIT_PER_MINUTE=60 LOADTEST_QUEUE_MAX_DEPTH=100 LOADTEST_API_KEYS='{"key-a":2,"key-b":2}'); script=loadtest/limiter.js ;;
  capacity) compose_env=(LOADTEST_RATE_LIMIT_PER_MINUTE=100000 LOADTEST_QUEUE_MAX_DEPTH=1000 LOADTEST_API_KEYS=); script=loadtest/capacity.js ;;
  overload) compose_env=(LOADTEST_RATE_LIMIT_PER_MINUTE=100000 LOADTEST_QUEUE_MAX_DEPTH=4 LOADTEST_API_KEYS=); script=loadtest/overload.js ;;
  *) echo "unknown load-test target: $target" >&2; exit 2 ;;
esac

for environment in "${compose_env[@]}"; do
  export "$environment"
done
label="${RUN_LABEL:-latest}"
result_file="/tmp/llm-chat-${target}-${label}-summary.json"
rm -f "$result_file"
docker compose down --remove-orphans
docker compose -f docker-compose.yml -f docker-compose.loadtest.yml up --build -d
trap 'docker compose down --remove-orphans' EXIT
until curl --fail --silent http://localhost:8080/ready >/dev/null; do sleep 2; done
docker compose exec -T ollama ollama pull "${MODEL:-tinyllama}" >/dev/null
max_queue_depth=0
if [[ "$target" == overload ]]; then
  max_queue_file="/tmp/llm-chat-overload-max-depth"
  printf '0\n' > "$max_queue_file"
  ( while true; do
      value="$(curl --silent http://localhost:8080/metrics | awk '$1 == "llm_chat_queue_depth" {print $2; exit}')"
      [[ -n "$value" ]] && awk -v file="$max_queue_file" -v new_value="$value" 'BEGIN {getline current < file; print (new_value > current ? new_value : current) > file; close(file)}'
      sleep 0.2
    done ) &
  scraper_pid=$!
fi
set +e
RESULT_FILE="$result_file" MODEL="${MODEL:-tinyllama}" k6 run --quiet "$script"
status=$?
set -e
if [[ "$target" == overload ]]; then
  kill "$scraper_pid" 2>/dev/null || true
  wait "$scraper_pid" 2>/dev/null || true
  max_queue_depth="$(cat "$max_queue_file")"
fi
(( status == 0 )) || exit "$status"
python3 scripts/render-loadtest-result.py "$target" "$result_file" "$max_queue_depth" "$label"
