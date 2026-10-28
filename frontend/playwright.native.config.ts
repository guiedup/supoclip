import { defineConfig } from "@playwright/test";

// Run against the installed local app without seeding or changing its database.
export default defineConfig({
  testDir: "./e2e",
  testMatch: "youtube-access.spec.ts",
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.NATIVE_TEST_URL || "http://localhost:3107",
    locale: "pt-BR",
    channel: process.platform === "win32" ? "msedge" : undefined,
    screenshot: "only-on-failure",
  },
});
