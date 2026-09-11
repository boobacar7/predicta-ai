import { formatProbability } from "@/lib/format/numbers";

const ROWS = [
  { key: "HOME" as const, label: "HOME", tone: "bg-home" },
  { key: "DRAW" as const, label: "DRAW", tone: "bg-draw" },
  { key: "AWAY" as const, label: "AWAY", tone: "bg-away" },
];

export function ProbabilityOverview({
  home,
  draw,
  away,
  favorite,
}: {
  home: number;
  draw: number;
  away: number;
  favorite: "HOME" | "DRAW" | "AWAY";
}) {
  const values = { HOME: home, DRAW: draw, AWAY: away };

  return (
    <div className="space-y-3" aria-label="Probabilités 1X2 du modèle">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface-elevated" aria-hidden="true">
        {ROWS.map((row) => (
          <span
            key={row.key}
            className={row.tone}
            style={{ width: `${Math.max(0, values[row.key]) * 100}%` }}
          />
        ))}
      </div>
      <dl className="grid gap-3 sm:grid-cols-3">
        {ROWS.map((row) => {
          const isFavorite = row.key === favorite;
          return (
            <div
              key={row.key}
              className="rounded-xl bg-surface-elevated px-3 py-3"
              data-favorite={isFavorite ? "true" : "false"}
            >
              <dt className="text-[11px] uppercase tracking-[0.16em] text-faint">
                {row.label}
                {isFavorite ? (
                  <span className="ml-2 normal-case tracking-normal text-ai-strong">Favori</span>
                ) : null}
              </dt>
              <dd className="mt-1 font-mono text-lg tabular text-foreground">
                {formatProbability(values[row.key])}
              </dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
