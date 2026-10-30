import { expect, test } from "@playwright/test";

test("a fresh browser opens the personal app without a login", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("#youtube-url")).toBeVisible();
  const response = await page.request.get("/api/auth/get-session");
  expect(response.ok()).toBeTruthy();
  expect(response.headers()["cache-control"]).toContain("no-store");
  const session = await response.json();
  expect(session.session.id).toBe(`local-${session.user.id}`);
  expect((await page.context().cookies()).filter(cookie => /session_token/.test(cookie.name))).toHaveLength(0);
  await expect(page.getByRole("button", { name: "Sair", exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Entrar", exact: true })).toHaveCount(0);
  expect((await page.request.get("/api/preferences")).ok()).toBeTruthy();
  expect((await page.request.get("/api/tasks")).ok()).toBeTruthy();
});

test("the same owner is restored after clearing cookies and opening another context", async ({ browser, page }) => {
  const owner = (await (await page.request.get("/api/auth/get-session")).json()).user.id;
  await page.context().clearCookies();
  await page.goto("/list");
  await expect(page.getByRole("heading", { name: "Biblioteca", exact: true })).toBeVisible();
  expect((await (await page.request.get("/api/auth/get-session")).json()).user.id).toBe(owner);
  const fresh = await browser.newContext();
  try {
    const response = await fresh.request.get(`${test.info().project.use.baseURL}/api/auth/get-session`);
    expect((await response.json()).user.id).toBe(owner);
  } finally { await fresh.close(); }
});

test("account screens redirect to the app and account deletion is hidden", async ({ page }) => {
  await page.goto("/sign-in?next=%2Flist");
  await page.waitForURL("**/list");
  for (const path of ["/sign-up", "/forgot-password", "/reset-password"]) {
    await page.goto(path);
    await page.waitForURL(`${test.info().project.use.baseURL}/`);
    await expect(page.locator("#youtube-url")).toBeVisible();
  }
  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Configurações", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: /Excluir conta/i })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Sair", exact: true })).toHaveCount(0);
});

test("cross-site access is refused and the backend still requires signed authentication", async ({ request }) => {
  const remote = await request.get("/api/auth/get-session", {
    headers: { Origin: "https://example.invalid", "Sec-Fetch-Site": "cross-site" },
  });
  expect(remote.status()).toBe(403);
  const forged = await request.get("/api/auth/get-session", { headers: { Host: "example.invalid:3107" } });
  expect(forged.status()).toBe(403);
  const unsigned = await request.get("http://127.0.0.1:8000/tasks");
  expect(unsigned.status()).toBe(401);
});
