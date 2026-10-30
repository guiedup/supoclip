import { SignIn } from "@/components/auth/sign-in";
import { AuthFrame } from "@/components/auth/auth-frame";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
import { redirect } from "next/navigation";
import { isLocalAutoLoginEnabled } from "@/server/local-session";
import { postAuthPath } from "@/lib/auth-redirect";

export default async function SignInPage({ searchParams }: { searchParams?: Promise<{ next?: string }> }) {
  if (isLocalAutoLoginEnabled()) {
    const next = (await searchParams)?.next ?? "/";
    redirect(postAuthPath(new URLSearchParams({ next }).toString()));
  }
  const t = await getTranslations("auth");
  return (
    <AuthFrame
      footer={<>{t("signInPage.noAccount")}{" "}<Link href="/sign-up" className="font-medium text-foreground underline-offset-4 hover:underline">{t("signInPage.signUp")}</Link></>}
    >
      <SignIn />
    </AuthFrame>
  );
}
