// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { assertLocalSessionRequest, getLocalOwnerSession, isLocalAutoLoginEnabled } from "./local-session";

const state = vi.hoisted(() => ({ findUnique: vi.fn() }));
vi.mock("@/lib/prisma", () => ({ default: { user: { findUnique: state.findUnique } } }));

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_LOCAL_AUTO_LOGIN", "true");
  vi.stubEnv("NEXT_PUBLIC_SELF_HOST", "true");
  vi.stubEnv("SELF_HOST", "true");
  vi.stubEnv("NEXT_PUBLIC_APP_URL", "http://localhost:3107");
  vi.stubEnv("BETTER_AUTH_URL", "http://localhost:3107");
  vi.stubEnv("LOCAL_AUTO_LOGIN_USER_ID", "existing-owner");
  state.findUnique.mockReset();
});
afterEach(() => vi.unstubAllEnvs());

const rejectedHeaders: Record<string, string>[] = [
  { host: "example.com:3107" }, { host: "localhost:3108" },
  { host: "localhost:3107", origin: "https://example.com" },
  { host: "localhost:3107", origin: "null" },
  { host: "localhost:3107", "x-forwarded-host": "example.com" },
  { host: "localhost:3107", "sec-fetch-site": "cross-site" },
  {},
];

describe("personal local mode", () => {
  it("requires explicit opt-in, a selected owner and local self-host URLs", () => {
    expect(isLocalAutoLoginEnabled()).toBe(true);
  });
  it.each([
    ["NEXT_PUBLIC_LOCAL_AUTO_LOGIN", "false"], ["NEXT_PUBLIC_SELF_HOST", "false"],
    ["SELF_HOST", "false"], ["LOCAL_AUTO_LOGIN_USER_ID", ""],
    ["NEXT_PUBLIC_APP_URL", "https://example.com"],
    ["BETTER_AUTH_URL", "http://localhost:3108"],
    ["BETTER_AUTH_URL", "https://localhost:3107"],
    ["NEXT_PUBLIC_APP_URL", "http://localhost.evil.test:3107"],
  ])("keeps normal authentication when %s is %s", (key, value) => {
    vi.stubEnv(key, value);
    expect(isLocalAutoLoginEnabled()).toBe(false);
  });

  it.each(["localhost:3107", "127.0.0.1:3107", "[::1]:3107"])("accepts direct loopback access on %s", host => {
    expect(() => assertLocalSessionRequest(new Headers({ host }))).not.toThrow();
  });
  it("supports the request URL for HTTP handlers without an explicit Host header", () => {
    expect(() => assertLocalSessionRequest(new Headers(), "http://localhost:3107/api/auth/get-session")).not.toThrow();
  });
  it.each(rejectedHeaders)("refuses remote, forwarded and cross-site owner access: %j", incoming => {
    expect(() => assertLocalSessionRequest(new Headers(incoming))).toThrow("Local access only");
  });
  it("returns the configured existing owner without exposing private database fields", async () => {
    const user = { id: "existing-owner", name: "Local owner", email: "local@example.test",
      emailVerified: false, image: null, createdAt: new Date(), updatedAt: new Date(), is_admin: false };
    state.findUnique.mockResolvedValue(user);
    const result = await getLocalOwnerSession();
    expect(result.user.id).toBe("existing-owner");
    expect(result.session.userId).toBe("existing-owner");
    expect(result.session.expiresAt.getTime()).toBeGreaterThan(Date.now());
    expect(state.findUnique).toHaveBeenCalledWith(expect.objectContaining({ where: { id: "existing-owner" } }));
    expect(state.findUnique.mock.calls[0][0].select).not.toHaveProperty("password_hash");
    expect(state.findUnique.mock.calls[0][0].select).not.toHaveProperty("stripe_customer_id");
  });
  it("does not silently switch accounts when the owner is missing", async () => {
    state.findUnique.mockResolvedValue(null);
    await expect(getLocalOwnerSession()).rejects.toThrow("Local owner is not configured");
  });
});
