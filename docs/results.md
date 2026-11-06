# Load-test results

The commands below generate measured sections in this file. Do not copy numbers into the
README without preserving the command, hardware, model, date, and git commit next to them.

```bash
make loadtest-limiter
make loadtest-baseline
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

<!-- LOADTEST:capacity-run-1:START -->
## Capacity load test (run-1)
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
<!-- LOADTEST:capacity-run-1:END -->
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

<!-- LOADTEST:baseline-run-1:START -->
## Baseline load test (run-1)
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T15:09:54Z
- Git commit: `faf67c018ff2b815b14b305f472c0f48a4d511e0`
- Exact command: `make loadtest-baseline`

Direct Ollama native `/api/chat` baseline. This is not an OpenAI gateway run.

| VUs | Successful req/s | Completion tokens/s | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) | 200 | Other |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.717 | 15.633 | 1419.502249 | 2343.8967531999997 | 2808.2080947199993 | 43 | 0 |
| 2 | 0.783 | 16.750 | 2041.384535 | 6714.666856399995 | 7410.8538144799995 | 47 | 0 |
| 4 | 0.867 | 25.450 | 4212.516462 | 9918.732946799999 | 10031.45261891 | 52 | 0 |
| 8 | 1.050 | 28.000 | 8277.275595 | 14646.116128199998 | 15546.718926900001 | 63 | 0 |
| 16 | 1.200 | 29.750 | 15245.110186 | 20285.743211150002 | 21489.90646260001 | 72 | 0 |
<!-- LOADTEST:baseline-run-1:END -->

<!-- LOADTEST:baseline-run-2:START -->
## Baseline load test (run-2)
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T15:16:41Z
- Git commit: `faf67c018ff2b815b14b305f472c0f48a4d511e0`
- Exact command: `make loadtest-baseline RUN_LABEL=run-2`

Direct Ollama native `/api/chat` baseline. This is not an OpenAI gateway run.

| VUs | Successful req/s | Completion tokens/s | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) | 200 | Other |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.533 | 15.717 | 1699.147868 | 4070.0548937000003 | 4255.2062234 | 32 | 0 |
| 2 | 0.533 | 13.950 | 2968.8125954999996 | 9159.923237449999 | 10361.44394082 | 32 | 0 |
| 4 | 0.883 | 25.533 | 4010.358955 | 9461.8232932 | 10752.0810602 | 53 | 0 |
| 8 | 1.133 | 27.300 | 6650.851318499999 | 12861.7546333 | 15097.941835019996 | 68 | 0 |
| 16 | 1.117 | 29.417 | 17136.680135 | 25507.4029384 | 27030.635248380004 | 67 | 0 |
<!-- LOADTEST:baseline-run-2:END -->

<!-- LOADTEST:capacity-run-2:START -->
## Capacity load test (run-2)
- Hardware: Intel(R) Core(TM) i5-8365U CPU @ 1.60GHz, 8 cores, 14Gi RAM, no GPU
- Model: tinyllama, Q4_0, 1.1B
- Date (UTC): 2026-11-06T16:48:14Z
- Git commit: `faf67c018ff2b815b14b305f472c0f48a4d511e0`
- Exact command: `make loadtest-capacity RUN_LABEL=run-2`

Capacity results include only 2xx responses in latency and token-rate columns.

| VUs | Successful req/s | Completion tokens/s | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) | 200 | 429 | 503 | Other |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.600 | 14.200 | 1382.478168 | 3724.343003 | 4526.889034449999 | 36 | 0 | 0 | 0 |
| 2 | 0.600 | 15.833 | 2918.8976924999997 | 7348.0034104999995 | 7832.56536245 | 36 | 0 | 0 | 0 |
| 4 | 1.167 | 24.750 | 3352.6175855 | 6041.83022515 | 10223.604287850001 | 70 | 0 | 0 | 0 |
| 8 | 1.167 | 26.667 | 6573.121607 | 11688.040562499997 | 13994.742429470005 | 70 | 0 | 0 | 0 |
| 16 | 1.383 | 29.317 | 13059.723719 | 17273.3608092 | 18108.059955039997 | 83 | 0 | 0 | 0 |

Streaming stage (4 VUs, 60s): `llm_chat_time_to_first_chunk_seconds` histogram values were collected from the gateway scrape after the run.
- Successful streams: 61; other statuses: 0; gateway histogram count: 61; p50: 0.5s; p95: 7.5s.
<!-- LOADTEST:capacity-run-2:END -->

<!-- BASELINE-COMPARISON:START -->
## Baseline comparison

The direct baseline uses Ollama native `/api/chat`; the gateway uses `/v1/chat/completions`. Differences represent gateway overhead plus noise, not a pure gateway-only measurement. Each side was run twice.

### Run 1: gateway versus direct Ollama

Sources: recorded `capacity-run-1` and `baseline-run-1` sections above; both were 2xx-only and include their own UTC date, command, and git commit.

| VUs | Metric | Gateway | Baseline | Absolute difference | Difference (%) |
|---:|---|---:|---:|---:|---:|
| 1 | Successful req/s | 0.483 | 0.717 | -0.234 | -32.64% |
| 1 | Completion tokens/s | 12.267 | 15.633 | -3.366 | -21.53% |
| 1 | p50 latency (ms) | 1663.094 | 1419.502 | 243.592 | 17.16% |
| 1 | p95 latency (ms) | 4753.595 | 2343.897 | 2409.698 | 102.81% |
| 1 | p99 latency (ms) | 5273.814 | 2808.208 | 2465.606 | 87.80% |
| 4 | Successful req/s | 0.933 | 0.867 | 0.066 | 7.61% |
| 4 | Completion tokens/s | 20.250 | 25.450 | -5.200 | -20.43% |
| 4 | p50 latency (ms) | 4099.842 | 4212.516 | -112.674 | -2.67% |
| 4 | p95 latency (ms) | 8571.046 | 9918.733 | -1347.687 | -13.59% |
| 4 | p99 latency (ms) | 12984.022 | 10031.453 | 2952.569 | 29.43% |

### Run 2: gateway versus direct Ollama

Sources: recorded `capacity-run-2` and `baseline-run-2` sections above; both were 2xx-only and include their own UTC date, command, and git commit.

| VUs | Metric | Gateway | Baseline | Absolute difference | Difference (%) |
|---:|---|---:|---:|---:|---:|
| 1 | Successful req/s | 0.600 | 0.533 | 0.067 | 12.57% |
| 1 | Completion tokens/s | 14.200 | 15.717 | -1.517 | -9.65% |
| 1 | p50 latency (ms) | 1382.478 | 1699.148 | -316.670 | -18.64% |
| 1 | p95 latency (ms) | 3724.343 | 4070.055 | -345.712 | -8.49% |
| 1 | p99 latency (ms) | 4526.889 | 4255.206 | 271.683 | 6.38% |
| 4 | Successful req/s | 1.167 | 0.883 | 0.284 | 32.16% |
| 4 | Completion tokens/s | 24.750 | 25.533 | -0.783 | -3.07% |
| 4 | p50 latency (ms) | 3352.618 | 4010.359 | -657.741 | -16.40% |
| 4 | p95 latency (ms) | 6041.830 | 9461.823 | -3419.993 | -36.15% |
| 4 | p99 latency (ms) | 10223.604 | 10752.081 | -528.477 | -4.92% |
<!-- BASELINE-COMPARISON:END -->
