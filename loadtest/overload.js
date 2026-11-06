import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";
const status200 = new Counter("overload_status_200");
const status503 = new Counter("overload_status_503");
const statusOther = new Counter("overload_status_other");
const retryAfterMissing = new Counter("overload_503_without_retry_after");

export const options = {
  scenarios: { overload: { executor: "constant-vus", vus: 32, duration: "30s" } },
};

export default function () {
  const response = http.post(
    `${baseUrl}/v1/chat/completions`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Reply with one short sentence." }],
      max_tokens: 64,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "180s" },
  );
  if (response.status === 200) status200.add(1);
  else if (response.status === 503) {
    status503.add(1);
    if (!response.headers["Retry-After"]) retryAfterMissing.add(1);
  } else statusOther.add(1);
  check(response, { "overload response is 200 or 503": (r) => r.status === 200 || r.status === 503 });
}

export function handleSummary(data) {
  const values = (name) => data.metrics[name]?.values || {};
  return {
    [__ENV.RESULT_FILE || "/tmp/overload-summary.json"]: JSON.stringify({
      status200: values("overload_status_200").count || 0,
      status503: values("overload_status_503").count || 0,
      statusOther: values("overload_status_other").count || 0,
      retryAfterMissing: values("overload_503_without_retry_after").count || 0,
    }, null, 2),
  };
}
