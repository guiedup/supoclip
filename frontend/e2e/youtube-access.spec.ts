import { expect, test } from "@playwright/test";

test.use({ locale: "pt-BR" });

test.beforeEach(async ({ page }) => {
  await page.route("**/api/auth/get-session**", route => route.fulfill({ json: {
    session: { id: "fixture", userId: "user", expiresAt: "2099-01-01T00:00:00Z" },
    user: { id: "user", name: "Local test", email: "local@supoclip.test" },
  } }));
  await page.route("**/api/fonts", route => route.fulfill({ json: { fonts: [] } }));
  await page.route("**/api/caption-templates", route => route.fulfill({ json: { templates: [] } }));
  await page.route("**/api/announcements**", route => route.fulfill({ json: { announcements: [] } }));
  await page.route("**/api/tasks/billing-summary", route => route.fulfill({ json: { monetization_enabled: false } }));
  await page.route("**/api/tasks/blocked/clips", route => route.fulfill({ json: { clips: [] } }));
});

const task = {
  id: "blocked", user_id: "user", source_title: "Source access test", source_type: "youtube",
  status: "error", clips_count: 0, created_at: "2026-10-28T12:00:00Z", updated_at: "2026-10-28T12:00:00Z",
};

test("YouTube access failures explain recovery and suppress futile resume", async ({ page }) => {
  await page.route("**/api/tasks/blocked", route => route.fulfill({ json: {
    ...task, error_code: "youtube_access_required",
    progress_message: "Untrusted provider detail with secret-token-do-not-display",
  } }));
  await page.goto("/tasks/blocked");
  await expect(page.getByRole("heading", { name: "O YouTube bloqueou esta importação" })).toBeVisible();
  await expect(page.getByText(/Obtenha o arquivo original/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retomar", exact: true })).toHaveCount(0);
  await expect(page.getByText(/secret-token-do-not-display/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Voltar ao início" })).toHaveAttribute("href", "/");
});

test("ordinary processing failures keep the resume action", async ({ page }) => {
  await page.route("**/api/tasks/blocked", route => route.fulfill({ json: {
    ...task, error_code: "analysis_error", progress_message: "Model timed out",
  } }));
  await page.goto("/tasks/blocked");
  await expect(page.getByRole("heading", { name: "Falha no processamento" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Retomar", exact: true })).toBeVisible();
});
