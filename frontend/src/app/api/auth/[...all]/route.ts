import { auth } from "@/lib/auth";
import { toNextJsHandler } from "better-auth/next-js";
import { isLocalAutoLoginEnabled } from "@/server/local-session";

const handlers = toNextJsHandler(auth.handler);
export const POST = handlers.POST;
export async function GET(request: Request) {
  const response = await handlers.GET(request);
  if (isLocalAutoLoginEnabled()) response.headers.set("Cache-Control", "private, no-store");
  return response;
}
