import { APIError } from "better-auth/api";
import prisma from "@/lib/prisma";
import { isLocalAutoLoginClientEnabled } from "@/lib/local-mode";

function loopbackUrl(value: string | undefined): URL | null {
  try {
    const url = new URL(value ?? "");
    if (!["http:", "https:"].includes(url.protocol)
      || !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
      || url.username || url.password) return null;
    return url;
  } catch { return null; }
}

export function isLocalAutoLoginEnabled(): boolean {
  const app = loopbackUrl(process.env.NEXT_PUBLIC_APP_URL);
  const auth = loopbackUrl(process.env.BETTER_AUTH_URL);
  return isLocalAutoLoginClientEnabled() && process.env.SELF_HOST === "true"
    && Boolean(process.env.LOCAL_AUTO_LOGIN_USER_ID?.trim())
    && Boolean(app && auth && app.port === auth.port && app.protocol === auth.protocol);
}

/** Do not trust forwarded hosts or cross-site requests to a local owner session. */
export function assertLocalSessionRequest(headers?: Headers, requestUrl?: string): void {
  const app = loopbackUrl(process.env.NEXT_PUBLIC_APP_URL);
  const host = headers?.get("host");
  const request = host ? loopbackUrl(`${app?.protocol ?? "http:"}//${host}`) : loopbackUrl(requestUrl);
  const allowed = (url: URL | null) => Boolean(
    app && url && app.port === url.port && app.protocol === url.protocol,
  );
  if (!allowed(request)) throw new APIError("FORBIDDEN", { message: "Local access only" });
  const forwarded = headers?.get("x-forwarded-host");
  if (forwarded && !allowed(loopbackUrl(`${app!.protocol}//${forwarded}`))) {
    throw new APIError("FORBIDDEN", { message: "Local access only" });
  }
  const origin = headers?.get("origin");
  if ((origin && !allowed(loopbackUrl(origin))) || headers?.get("sec-fetch-site") === "cross-site") {
    throw new APIError("FORBIDDEN", { message: "Local access only" });
  }
}

export async function getLocalOwnerSession() {
  const user = await prisma.user.findUnique({
    where: { id: process.env.LOCAL_AUTO_LOGIN_USER_ID!.trim() },
    // Password hashes, billing identifiers and other private fields stay server-side.
    select: { id: true, name: true, email: true, emailVerified: true, image: true,
      createdAt: true, updatedAt: true, is_admin: true },
  });
  if (!user) throw new APIError("SERVICE_UNAVAILABLE", { message: "Local owner is not configured" });
  const now = new Date();
  return {
    user,
    session: {
      id: `local-${user.id}`, userId: user.id,
      // A display-only session; this is not a usable Better Auth cookie/token.
      token: "local-owner-session", createdAt: now, updatedAt: now,
      expiresAt: new Date(now.getTime() + 24 * 60 * 60 * 1000),
      ipAddress: "127.0.0.1", userAgent: "SupoClip local",
    },
  };
}
