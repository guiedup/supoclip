// @vitest-environment node
import { afterAll, expect, it, vi } from "vitest";
import { memoryAdapter } from "better-auth/adapters/memory";

const state = vi.hoisted(() => ({
  database: { user: [], session: [], account: [], verification: [] },
  findUnique: vi.fn(),
}));
vi.mock("better-auth/adapters/prisma", () => ({ prismaAdapter: () => memoryAdapter(state.database) }));
vi.mock("@/lib/prisma", () => ({ default: { user: { findUnique: state.findUnique } } }));
vi.mock("@/server/account-deletion", () => ({ prepareAccountDeletion: vi.fn() }));
vi.mock("@/server/backend-api", () => ({ fetchBackend: vi.fn() }));

vi.stubEnv("NEXT_PUBLIC_LOCAL_AUTO_LOGIN", "true");
vi.stubEnv("NEXT_PUBLIC_SELF_HOST", "true");
vi.stubEnv("SELF_HOST", "true");
vi.stubEnv("NEXT_PUBLIC_APP_URL", "http://localhost:3107");
vi.stubEnv("BETTER_AUTH_URL", "http://localhost:3107");
vi.stubEnv("LOCAL_AUTO_LOGIN_USER_ID", "existing-owner");
vi.stubEnv("BETTER_AUTH_SECRET", "test-local-mode-secret-at-least-32-characters");
state.findUnique.mockResolvedValue({ id: "existing-owner", name: "Local owner", email: "local@example.test",
  emailVerified: false, image: null, createdAt: new Date(), updatedAt: new Date(), is_admin: false });
const { auth } = await import("./auth");
afterAll(() => vi.unstubAllEnvs());

it("resolves the existing owner through server APIs without cookies or a sign-in", async () => {
  const session = await auth.api.getSession({ headers: new Headers({ host: "localhost:3107" }) });
  expect(session?.user.id).toBe("existing-owner");
  expect(state.database.session).toHaveLength(0);
});
it("also supplies the browser session endpoint without creating login cookies", async () => {
  const response = await auth.handler(new Request("http://localhost:3107/api/auth/get-session"));
  expect(response.status).toBe(200);
  expect((await response.json()).user.id).toBe("existing-owner");
  expect(response.headers.get("set-cookie")).toBeNull();
});
it("refuses a cross-site request for the local owner", async () => {
  const response = await auth.handler(new Request("http://localhost:3107/api/auth/get-session", {
    headers: { Origin: "https://example.test", "Sec-Fetch-Site": "cross-site" },
  }));
  expect(response.status).toBe(403);
});
it("does not allow the local owner to be signed out or deleted through auth endpoints", async () => {
  for (const route of ["sign-out", "delete-user", "sign-up/email"]) {
    const response = await auth.handler(new Request(`http://localhost:3107/api/auth/${route}`, {
      method: "POST", headers: { Origin: "http://localhost:3107", "Content-Type": "application/json" }, body: "{}",
    }));
    expect(response.status).toBe(403);
  }
});
