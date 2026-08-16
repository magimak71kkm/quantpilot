import { defineConfig } from "@playwright/test";

const PROTOTYPE = process.env.QP_PROTOTYPE_URL || "http://localhost:8090/prototype.html";
const API = process.env.QP_API_URL || "http://localhost:8080";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: PROTOTYPE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1440, height: 900 },
  },
  webServer: process.env.QP_SKIP_WEBSERVER
    ? undefined
    : {
        // 프로토타입 HTML을 8090 포트에 정적 서빙 (파이썬 내장 서버)
        command:
          "python3 -m http.server 8090 --bind 127.0.0.1 --directory ../../proto",
        port: 8090,
        reuseExistingServer: true,
        stdout: "ignore",
        stderr: "pipe",
      },
  expect: { timeout: 10_000 },
  projects: [
    {
      name: "chromium",
      use: { channel: undefined, browserName: "chromium" },
    },
  ],
  metadata: { api: API },
});
