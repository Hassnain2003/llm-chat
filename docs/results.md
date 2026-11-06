# Load-test results

The commands below generate measured sections in this file. Do not copy numbers into the
README without preserving the command, hardware, model, date, and git commit next to them.

```bash
make loadtest-limiter
make loadtest-capacity
make loadtest-overload
```

The capacity table is a performance benchmark only when the 2xx status count is at least 99%
of requests. Otherwise, treat the run as an overload or configuration test and report its status
breakdown instead.

<!-- LOADTEST:limiter:START -->
## Limiter load test
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T14:25:06Z
- Git commit: `c6facebbe3fc7fc0f932b4ae0ddd85e25eddc7b5`
- Exact command: `make loadtest-limiter`

Limiter verification, not a performance benchmark.

| 200 responses | 429 responses | 429 without Retry-After | key-b 200 responses |
|---:|---:|---:|---:|
| 4 | 8 | 0 | 2 |
<!-- LOADTEST:limiter:END -->

<!-- LOADTEST:capacity:START -->
## Capacity load test
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T14:32:54Z
- Git commit: `c6facebbe3fc7fc0f932b4ae0ddd85e25eddc7b5`
- Exact command: `make loadtest-capacity`

Capacity results include only 2xx responses in latency and token-rate columns.

| VUs | Successful req/s | Completion tokens/s | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) | 200 | 429 | 503 | Other |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.483 | 12.267 | 1663.093962 | 4753.594763599998 | 5273.814026239999 | 29 | 0 | 0 | 0 |
| 2 | 0.550 | 13.650 | 3363.906428 | 8366.191417199998 | 9101.05991408 | 33 | 0 | 0 | 0 |
| 4 | 0.933 | 20.250 | 4099.8420595 | 8571.0457525 | 12984.021508200005 | 56 | 0 | 0 | 0 |
| 8 | 1.083 | 23.083 | 7782.490377 | 11542.3006128 | 12449.03992548 | 65 | 0 | 0 | 0 |
| 16 | 1.167 | 26.467 | 15136.0638445 | 21067.354257199997 | 22043.396183400004 | 70 | 0 | 0 | 0 |

Streaming stage (4 VUs, 60s): `llm_chat_time_to_first_chunk_seconds` histogram values were collected from the gateway scrape after the run.
- Successful streams: 58; other statuses: 0; gateway histogram count: 58; p50: 0.5s; p95: 10s.
<!-- LOADTEST:capacity:END -->
<!-- LOADTEST:overload:START -->
## Overload load test
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T14:25:51Z
- Git commit: `c6facebbe3fc7fc0f932b4ae0ddd85e25eddc7b5`
- Exact command: `make loadtest-overload`

| 200 responses | 503 responses | Other statuses | 503 without Retry-After | Maximum observed queue depth |
|---:|---:|---:|---:|---:|
| 21 | 8393 | 0 | 0 | 4.0 |
<!-- LOADTEST:overload:END -->
