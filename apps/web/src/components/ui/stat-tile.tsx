import { cn } from "@/lib/cn";

/**
 * Compact labelled figure used inside cards.
 *
 * Values arrive already formatted as strings, so the tile never has to decide how
 * a missing measurement is displayed. Monospaced tabular digits keep columns of
 * probabilities and odds aligned.
 */
export function StatTile({
  label,
  value,
  hint,
  tone = "default",
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "ai" | "value";
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl bg-surface-elevated px-3 py-2", className)}>
      <dt className="text-[11px] uppercase tracking-[0.16em] text-faint">{label}</dt>
      <dd
        className={cn(
          "mt-1 font-mono text-sm tabular",
          tone === "ai" && "text-ai-strong",
          tone === "value" && "text-value",
        )}
      >
        {value}
      </dd>
      {hint ? <p className="mt-1 text-[11px] text-faint">{hint}</p> : null}
    </div>
  );
}
