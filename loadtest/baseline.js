import http from "k6/http";
import { check, sleep } from "k6";
import { Counter, Trend } from "k6/metrics";
import exec from "k6/execution";

const baseUrl = __ENV.BASELINE_URL || "http://localhost:11434";
const stages = [1, 2, 4, 8, 16];
const metrics = Object.fromEntries(stages.map((stage) => [
  stage,
  {
    success: new Counter(`baseline_${stage}_success`),
    tokens: new Counter(`baseline_${stage}_completion_tokens`),
    latency: new Trend(`baseline_${stage}_success_latency`, true),
    other: new Counter(`baseline_${stage}_status_other`),
  },
]));

export const options = {
  scenarios: Object.fromEntries(stages.map((stage, index) => [
    `users_${stage}`,
    {
      executor: "constant-vus",
      vus: stage,
      duration: "60s",
      startTime: `${index * 65}s`,
    },
  ])),
  summaryTrendStats: ["avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"],
};

export function setup() {
  const warmup = http.post(
    `${baseUrl}/api/chat`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Warm up with one word." }],
      options: { num_predict: 64 },
      stream: false,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "180s" },
  );
  check(warmup, { "baseline warm-up completed": (r) => r.status === 200 });
  sleep(15);
}

export default function () {
  const stage = Number(exec.scenario.name.replace("users_", ""));
  const response = http.post(
    `${baseUrl}/api/chat`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Reply with one short sentence." }],
      options: { num_predict: 64 },
      stream: false,
    }),
    { headers: { "Content-Type": "application/json" }, timeout: "180s" },
  );
  if (response.status === 200) {
    metrics[stage].success.add(1);
    metrics[stage].latency.add(response.timings.duration);
    metrics[stage].tokens.add(response.json("eval_count") || 0);
  } else {
    metrics[stage].other.add(1);
  }
  check(response, { "baseline response is successful": (r) => r.status === 200 });
}

export function handleSummary(data) {
  const values = (name) => data.metrics[name]?.values || {};
  const summary = { stages: {} };
  for (const stage of stages) {
    summary.stages[stage] = {
      successful: values(`baseline_${stage}_success`).count || 0,
      completionTokens: values(`baseline_${stage}_completion_tokens`).count || 0,
      statusOther: values(`baseline_${stage}_status_other`).count || 0,
      latency: values(`baseline_${stage}_success_latency`),
    };
  }
  return {
    [__ENV.RESULT_FILE || "/tmp/baseline-summary.json"]: JSON.stringify(summary, null, 2),
  };
}
