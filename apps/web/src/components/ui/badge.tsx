import { cn } from "@/lib/cn";
import type { HTMLAttributes } from "react";

export function Badge({
  className,
  tone = "neutral",
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: "neutral" | "ai" | "value" | "warning" | "risk" | "muted";
}) {
  const tones = {
    neutral: "bg-surface-elevated text-muted-strong border-border",
    ai: "bg-ai-soft text-ai-strong border-ai/20",
    value: "bg-value-soft text-value border-value/20",
    warning: "bg-warning-soft text-warning border-warning/20",
    risk: "bg-risk-soft text-risk border-risk/20",
    muted: "bg-transparent text-muted border-border",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
