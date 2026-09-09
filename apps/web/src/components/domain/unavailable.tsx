import { cn } from "@/lib/cn";
import type { HTMLAttributes } from "react";

export function Unavailable({
  label,
  reason,
  className,
  ...props
}: HTMLAttributes<HTMLDivElement> & { label: string; reason: string }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-dashed border-border-strong bg-surface-elevated/50 px-4 py-3",
        className,
      )}
      {...props}
    >
      <p className="text-sm text-foreground">{label} indisponible</p>
      <p className="mt-1 text-xs text-muted">{reason} Cette absence n’est pas une valeur nulle.</p>
    </div>
  );
}
