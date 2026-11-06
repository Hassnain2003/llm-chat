import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import exec from "k6/execution";

const baseUrl = __ENV.BASE_URL || "http://localhost:8080";
const stages = [1, 2, 4, 8, 16];
const stageMetrics = Object.fromEntries(
  stages.map((stage) => [
    stage,
    {
      success: new Counter(`capacity_${stage}_success`),
      status429: new Counter(`capacity_${stage}_status_429`),
      status503: new Counter(`capacity_${stage}_status_503`),
      statusOther: new Counter(`capacity_${stage}_status_other`),
      tokens: new Counter(`capacity_${stage}_completion_tokens`),
      latency: new Trend(`capacity_${stage}_success_latency`, true),
    },
  ]),
);
const streamTtfb = new Trend("capacity_stream_ttfb", true);
const streamSuccess = new Counter("capacity_stream_success");
const streamStatusOther = new Counter("capacity_stream_status_other");

export const options = {
  scenarios: {
    ...Object.fromEntries(
      stages.map((stage, index) => [
        `users_${stage}`,
        {
          executor: "constant-vus",
          vus: stage,
          duration: "60s",
          startTime: `${index * 65}s`,
          tags: { capacity_stage: String(stage) },
        },
      ]),
    ),
    stream: {
      executor: "constant-vus",
      vus: 4,
      duration: "60s",
      startTime: "325s",
      tags: { capacity_stage: "stream" },
    },
  },
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

export function setup() {
  const warmup = http.post(
    `${baseUrl}/v1/chat/completions`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Warm up with one word." }],
      max_tokens: 64,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "180s" },
  );
  check(warmup, { "warm-up request completed": (r) => r.status === 200 });
  sleep(15);
}

export default function () {
  const stage = Number(exec.scenario.name.replace("users_", ""));
  const metrics = stageMetrics[stage];
  if (!metrics) return streamRequest();
  const response = http.post(
    `${baseUrl}/v1/chat/completions`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Reply with one short sentence." }],
      max_tokens: 64,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "180s" },
  );
  if (response.status === 200) {
    metrics.success.add(1);
    metrics.latency.add(response.timings.duration);
    metrics.tokens.add(response.json("usage.completion_tokens") || 0);
  } else if (response.status === 429) {
    metrics.status429.add(1);
  } else if (response.status === 503) {
    metrics.status503.add(1);
  } else {
    metrics.statusOther.add(1);
  }
  check(response, { "capacity response is successful": (r) => r.status === 200 });
}

function streamRequest() {
  const response = http.post(
    `${baseUrl}/v1/chat/completions`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Reply with one short sentence." }],
      max_tokens: 64,
      stream: true,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "180s" },
  );
  if (response.status === 200) {
    streamTtfb.add(response.timings.waiting);
    streamSuccess.add(1);
  } else {
    streamStatusOther.add(1);
  }
  check(response, { "stream response is successful": (r) => r.status === 200 });
}

export function handleSummary(data) {
  const values = (name) => data.metrics[name]?.values || {};
  const summary = { stages: {}, stream: {
    successful: values("capacity_stream_success").count || 0,
    other: values("capacity_stream_status_other").count || 0,
    ttfb: values("capacity_stream_ttfb"),
  } };
  for (const stage of stages) {
    summary.stages[stage] = {
      successful: values(`capacity_${stage}_success`).count || 0,
      status429: values(`capacity_${stage}_status_429`).count || 0,
      status503: values(`capacity_${stage}_status_503`).count || 0,
      statusOther: values(`capacity_${stage}_status_other`).count || 0,
      completionTokens: values(`capacity_${stage}_completion_tokens`).count || 0,
      latency: values(`capacity_${stage}_success_latency`),
    };
  }
  return {
    [__ENV.RESULT_FILE || "/tmp/capacity-summary.json"]: JSON.stringify(summary, null, 2),
  };
}
