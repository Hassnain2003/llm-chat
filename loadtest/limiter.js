import http from "k6/http";
import { check } from "k6";
import { Counter } from "k6/metrics";

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";
const status200 = new Counter("limiter_status_200");
const status429 = new Counter("limiter_status_429");
const retryAfterMissing = new Counter("limiter_429_without_retry_after");
const keyBSuccess = new Counter("limiter_key_b_success");

export const options = {
  scenarios: {
    verification: { executor: "shared-iterations", vus: 1, iterations: 3 },
  },
};

function request(apiKey) {
  const response = http.post(
    `${baseUrl}/v1/chat/completions`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Reply with one word." }],
      max_tokens: 4,
    }),
    {
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      tags: { limiter_key: apiKey },
    },
  );
  if (response.status === 200) status200.add(1);
  if (response.status === 429) {
    status429.add(1);
    if (!response.headers["Retry-After"]) retryAfterMissing.add(1);
  }
  if (apiKey === "key-b" && response.status === 200) keyBSuccess.add(1);
  check(response, {
    "limiter response is 200 or 429": (r) => r.status === 200 || r.status === 429,
  });
  return response;
}

export default function () {
  request("key-a");
  request("key-a");
  request("key-a");
  request("key-b");
}

export function handleSummary(data) {
  const values = (name) => data.metrics[name]?.values || {};
  return {
    [__ENV.RESULT_FILE || "/tmp/limiter-summary.json"]: JSON.stringify(
      { status200: values("limiter_status_200").count || 0,
        status429: values("limiter_status_429").count || 0,
        retryAfterMissing: values("limiter_429_without_retry_after").count || 0,
        keyBSuccess: values("limiter_key_b_success").count || 0 },
      null,
      2,
    ),
  };
}
