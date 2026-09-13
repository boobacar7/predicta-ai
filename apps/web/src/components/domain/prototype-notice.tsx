import { Badge } from "@/components/ui/badge";
import type { ReactNode } from "react";

/**
 * Labels a remaining prototype surface so it cannot be read as the football engine.
 */
export function PrototypeNotice({ children }: { children: ReactNode }) {
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border bg-surface px-4 py-3"
    >
      <Badge tone="muted">Prototype</Badge>
      <p className="text-xs text-muted">{children}</p>
    </div>
  );
}
