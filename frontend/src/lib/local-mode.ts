/** Explicit opt-in for a personal, loopback-only installation. */
export function isLocalAutoLoginClientEnabled(): boolean {
  return process.env.NEXT_PUBLIC_LOCAL_AUTO_LOGIN === "true"
    && process.env.NEXT_PUBLIC_SELF_HOST === "true";
}
