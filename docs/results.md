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
- Date (UTC): 2026-11-06T14:08:19Z
- Git commit: `6f5c6916de2306a0ca4651a1c016825bf3951836`
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
- Date (UTC): 2026-11-06T14:24:26Z
- Git commit: `6f5c6916de2306a0ca4651a1c016825bf3951836`
- Exact command: `make loadtest-capacity`

Capacity results include only 2xx responses in latency and token-rate columns.

| VUs | Successful req/s | Completion tokens/s | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) | 200 | 429 | 503 | Other |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.533 | 13.400 | 1445.860181 | 4503.7995321 | 4842.331083460001 | 32 | 0 | 0 | 0 |
| 2 | 0.617 | 15.167 | 2868.14453 | 8326.6986192 | 8497.57320992 | 37 | 0 | 0 | 0 |
| 4 | 0.917 | 21.667 | 3827.261342 | 11057.4988991 | 11221.0026021 | 55 | 0 | 0 | 0 |
| 8 | 1.017 | 24.983 | 8160.895608 | 12401.392916 | 14038.678627599998 | 61 | 0 | 0 | 0 |
| 16 | 1.133 | 27.967 | 16289.771428 | 24007.019066899997 | 26183.70995787 | 68 | 0 | 0 | 0 |

Streaming stage (4 VUs, 60s): `llm_chat_time_to_first_chunk_seconds` histogram values were collected from the gateway scrape after the run.
- Successful streams: 46; other statuses: 0; gateway histogram count: 46; p50: 0.75s; p95: inf.
<!-- LOADTEST:capacity:END -->
<!-- LOADTEST:overload:START -->
## Overload load test
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T14:17:19Z
- Git commit: `6f5c6916de2306a0ca4651a1c016825bf3951836`
- Exact command: `make loadtest-overload`

| 200 responses | 503 responses | Other statuses | 503 without Retry-After | Maximum observed queue depth |
|---:|---:|---:|---:|---:|
| 26 | 9101 | 0 | 0 | 4.0 |
<!-- LOADTEST:overload:END -->
