"use client";

import { AppShell } from "@/components/layout/app-shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryProvider } from "@/lib/query/client";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryProvider>
      <TooltipProvider>
        <AppShell>{children}</AppShell>
      </TooltipProvider>
    </QueryProvider>
  );
}
