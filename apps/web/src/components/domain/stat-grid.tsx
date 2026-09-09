import { MetricCard } from "@/components/domain/metric-card";
import { Unavailable } from "@/components/domain/unavailable";
import { formatNumber } from "@/lib/format/numbers";
import type { NamedStat } from "@/types/api";

/**
 * Renders a list of named statistics with their availability.
 *
 * A stat the source declares unavailable is shown as an explicit gap rather than
 * a blank tile or a zero, which is the rule the product spec sets for missing
 * measurements. The unit is appended only when the value itself exists.
 */
export function StatGrid({
  stats,
  className = "grid gap-4 sm:grid-cols-2 xl:grid-cols-3",
}: {
  stats: readonly NamedStat[];
  className?: string;
}) {
  if (stats.length === 0) {
    return (
      <p className="text-sm text-muted">Aucun indicateur n&apos;est publié pour cette entité.</p>
    );
  }

  return (
    <div className={className}>
      {stats.map((stat) =>
        stat.quality.availability === "unavailable" || stat.value === null ? (
          <Unavailable
            key={stat.key}
            label={stat.label}
            reason={stat.quality.note ?? "Cet indicateur n'est pas fourni par la source."}
          />
        ) : (
          <MetricCard
            key={stat.key}
            label={stat.label}
            value={`${formatNumber(stat.value)}${stat.unit ? ` ${stat.unit}` : ""}`}
            hint={stat.quality.note ?? undefined}
          />
        ),
      )}
    </div>
  );
}
