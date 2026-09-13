"use client";

import { safeNextPath } from "@/data/http/auth";
import { useAuthSession } from "@/features/auth/session-context";
import { getConfig, type WebConfig } from "@/lib/config";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

/** Login stays mounted; product routes skip the gate when AUTH_BYPASS is on (never in production). */
export function shouldGateAuth(
  pathname: string,
  config: Pick<WebConfig, "deploymentEnv" | "authBypass">,
): boolean {
  if (pathname === "/login") return false;
  if (config.authBypass) return false;
  return config.deploymentEnv === "staging" || config.deploymentEnv === "production";
}

function needsAuthGate(pathname: string): boolean {
  return shouldGateAuth(pathname, getConfig());
}

export function AuthGate({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { status } = useAuthSession();
  const gated = needsAuthGate(pathname);

  useEffect(() => {
    if (!gated) return;
    if (status === "loading" || status === "disabled" || status === "bypassed") return;
    if (status === "authenticated") return;
    router.replace(`/login?next=${encodeURIComponent(safeNextPath(pathname))}`);
  }, [gated, pathname, router, status]);

  if (gated && (status === "loading" || status === "anonymous")) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <p className="text-sm text-muted">Vérification de la session…</p>
      </div>
    );
  }

  return <>{children}</>;
}
