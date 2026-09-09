import { formatProbability } from "@/lib/format/numbers";
import { cn } from "@/lib/cn";
import type { ProbabilityOutcome } from "@/types/api";

export function ProbabilityBar({
  outcomes,
  className,
}: {
  outcomes: ProbabilityOutcome[];
  className?: string;
}) {
  const colors = ["bg-home", "bg-draw", "bg-away", "bg-ai-strong"];
  const summary = outcomes
    .map((outcome) => `${outcome.label} ${formatProbability(outcome.calibrated_probability)}`)
    .join(", ");

  return (
    <div className={cn("space-y-2", className)}>
      <p className="sr-only">Probabilités calibrées : {summary}</p>
      <div className="flex h-2 overflow-hidden rounded-full bg-surface-elevated" aria-hidden="true">
        {outcomes.map((outcome, index) => {
          const width = (outcome.calibrated_probability ?? 0) * 100;
          return (
            <div
              key={outcome.selection}
              className={cn(colors[index % colors.length], "h-full")}
              style={{ width: `${width}%` }}
            />
          );
        })}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
        {outcomes.map((outcome, index) => (
          <li key={outcome.selection} className="flex items-center gap-1.5">
            <span
              className={cn("size-1.5 rounded-full", colors[index % colors.length])}
              aria-hidden="true"
            />
            <span>{outcome.label}</span>
            <span className="font-mono text-foreground tabular">
              {formatProbability(outcome.calibrated_probability)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
