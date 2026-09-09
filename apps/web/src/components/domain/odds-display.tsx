import { formatAbsolute } from "@/lib/format/dates";
import { formatDecimalOdds, formatProbability } from "@/lib/format/numbers";
import type { OddsSnapshot } from "@/types/api";

export function OddsDisplay({ odds }: { odds: OddsSnapshot | null }) {
  if (!odds) {
    return (
      <p className="text-sm text-muted">
        Cote indisponible. Aucune valeur n’est interpolée.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted">
        Cotes observées · {odds.bookmaker} · {formatAbsolute(odds.observed_at)}
        {odds.quality.availability === "stale" ? " · snapshot ancien" : ""}
      </p>
      <ul className="grid gap-2 sm:grid-cols-3">
        {odds.selections.map((selection) => (
          <li
            key={selection.selection}
            className="rounded-xl border border-border bg-surface-elevated px-3 py-2"
          >
            <p className="text-xs text-muted">{selection.label}</p>
            <p className="mt-1 font-mono text-lg tabular text-foreground">
              {formatDecimalOdds(selection.decimal_odds)}
            </p>
            <p className="text-xs text-faint">
              Implicite {formatProbability(selection.implied_probability_raw)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
