# Load-test results

This file is intentionally unmeasured until `make loadtest` is run against a live gateway
and model backend. Do not add numbers without preserving the command output.

Before filling this file, record:

- Hardware: CPU, GPU, RAM, and storage.
- Model: exact model name and quantization.
- Date and time in UTC.
- Command used, including `BASE_URL` and `MODEL` if set.

Run:

```bash
make dev
make loadtest
```

The command writes the measured k6 or fallback output below this section.
