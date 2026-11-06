import http from "k6/http";
import { check } from "k6";

export const options = {
  scenarios: {
    users_10: { executor: "constant-vus", vus: 10, duration: "30s", startTime: "0s" },
    users_50: { executor: "constant-vus", vus: 50, duration: "30s", startTime: "35s" },
    users_100: { executor: "constant-vus", vus: 100, duration: "30s", startTime: "70s" },
  },
};

export default function () {
  const response = http.post(
    `${__ENV.BASE_URL || "http://localhost:8080"}/v1/chat/completions`,
    JSON.stringify({
      model: __ENV.MODEL || "tinyllama",
      messages: [{ role: "user", content: "Reply with one short sentence." }],
    }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(response, { "status is successful": (r) => r.status === 200 });
}
