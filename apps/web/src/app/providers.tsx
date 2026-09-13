"use client";

import { AppShell } from "@/components/layout/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthGate } from "@/features/auth/auth-gate";
import { AuthSessionProvider } from "@/features/auth/session-context";
import { QueryProvider } from "@/lib/query/client";
import { ThemeProvider } from "@/lib/theme/theme-provider";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <ThemeProvider>
        <TooltipProvider>
          <AuthSessionProvider>
            <AuthGate>
              <AppShell>{children}</AppShell>
            </AuthGate>
          </AuthSessionProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}
