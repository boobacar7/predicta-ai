import { Card, CardBody } from "@/components/ui/card";
import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export function MetricCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  tone?: "default" | "ai" | "value";
}) {
  return (
    <Card>
      <CardBody>
        <p className="text-xs uppercase tracking-[0.16em] text-faint">{label}</p>
        <p
          className={cn(
            "mt-2 font-mono text-2xl tabular",
            tone === "ai" && "text-ai-strong",
            tone === "value" && "text-value",
          )}
        >
          {value}
        </p>
        {hint ? <p className="mt-2 text-xs text-muted">{hint}</p> : null}
      </CardBody>
    </Card>
  );
}
