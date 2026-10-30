import { defineConfig } from "@playwright/test";

// Installed personal app only: no database seeding, accounts or saved cookies.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "local-auto-login.spec.ts",
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  use: {
    baseURL: process.env.NATIVE_TEST_URL || "http://localhost:3107",
    locale: "pt-BR",
    channel: process.platform === "win32" ? "msedge" : undefined,
    screenshot: "only-on-failure",
  },
});
