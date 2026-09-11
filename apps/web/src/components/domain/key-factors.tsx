import { FACTOR_DIRECTION_LABELS, formatFactorValue } from "@/features/ai-analyst/format";
import type { FootballAnalystFactor } from "@/types/api";

export function KeyFactors({ factors }: { factors: FootballAnalystFactor[] }) {
  return (
    <section aria-labelledby="analyst-key-factors">
      <h3 id="analyst-key-factors" className="text-sm font-medium">
        Key Factors
      </h3>
      {factors.length === 0 ? (
        <p className="mt-2 text-sm text-muted">Information indisponible</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {factors.map((factor) => (
            <li
              key={`${factor.type}-${factor.label}`}
              className="flex flex-wrap items-start justify-between gap-3 rounded-xl bg-surface-elevated px-3 py-2"
            >
              <div className="min-w-0">
                <p className="text-sm text-foreground">{factor.label}</p>
                <p className="mt-0.5 text-[11px] uppercase tracking-[0.14em] text-faint">
                  {factor.type.replaceAll("_", " ")}
                  {factor.direction
                    ? ` · ${FACTOR_DIRECTION_LABELS[factor.direction]}`
                    : ""}
                </p>
              </div>
              <p className="font-mono text-sm tabular text-muted-strong">
                {formatFactorValue(factor)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
