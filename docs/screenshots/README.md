# Grafana screenshots

After running `make loadtest-capacity`, open Grafana at `http://localhost:3000` and capture:

1. Queue depth during the 1/2/4/8/16-user stages.
2. Request latency and the time-to-first-chunk histogram.
3. Active requests while a capacity stage is running.
4. Backend-reported tokens/sec and streaming chunks/sec.
5. HPA replica count during an autoscaling test; this is unavailable until the optional
   custom-metrics path is verified.
6. `kubectl get pods -n llm-chat` showing readiness and restart counts.

Save the images in this directory with the UTC date and scenario in each filename. Do not add
unmeasured screenshots or screenshots from a different model/configuration.
