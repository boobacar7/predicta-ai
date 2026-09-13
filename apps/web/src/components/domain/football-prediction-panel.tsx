import { CandidateModelNotice, ModelStatusBadge } from "@/components/domain/model-status";
import { formatAbsolute } from "@/lib/format/dates";
import { formatProbability } from "@/lib/format/numbers";
import type { FootballModelPrediction } from "@/types/api";

const ROWS = [
  { key: "HOME" as const, label: "HOME", tone: "bg-home" },
  { key: "DRAW" as const, label: "DRAW", tone: "bg-draw" },
  { key: "AWAY" as const, label: "AWAY", tone: "bg-away" },
] as const;

/**
 * Displays `GET /football/predictions/{match_id}` as published.
 *
 * No favorite is inferred: that label exists only on the AI Analyst report.
 */
export function FootballPredictionPanel({
  prediction,
  variant = "full",
}: {
  prediction: FootballModelPrediction;
  variant?: "full" | "compact";
}) {
  const compact = variant === "compact";

  return (
    <section
      className={compact ? "space-y-3" : "space-y-4"}
      aria-label={compact ? "Prédiction moteur" : undefined}
      aria-labelledby={compact ? undefined : "football-prediction-heading"}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        {compact ? (
          <p className="text-xs uppercase tracking-[0.16em] text-faint">Prédiction moteur</p>
        ) : (
          <h2 id="football-prediction-heading" className="text-lg font-medium">
            Prédiction moteur
          </h2>
        )}
        <ModelStatusBadge version={prediction.model_version} status={prediction.model_status} />
      </div>

      {compact ? null : (
        <CandidateModelNotice version={prediction.model_version} status={prediction.model_status} />
      )}

      <Football1x2Probabilities prediction={prediction} compact={compact} />

      {compact ? null : (
        <dl className="grid gap-3 text-xs text-muted sm:grid-cols-2">
          <div>
            <dt className="uppercase tracking-[0.14em] text-faint">Dataset</dt>
            <dd className="mt-1 font-mono text-foreground">{prediction.dataset_version}</dd>
          </div>
          <div>
            <dt className="uppercase tracking-[0.14em] text-faint">Cutoff</dt>
            <dd className="mt-1 text-foreground">{formatAbsolute(prediction.cutoff_at)}</dd>
          </div>
        </dl>
      )}
    </section>
  );
}

export function Football1x2Probabilities({
  prediction,
  compact = false,
}: {
  prediction: FootballModelPrediction;
  compact?: boolean;
}) {
  const values = {
    HOME: prediction.home_probability,
    DRAW: prediction.draw_probability,
    AWAY: prediction.away_probability,
  };

  return (
    <div className="space-y-3" aria-label="Probabilités 1X2 du modèle">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface-elevated" aria-hidden="true">
        {ROWS.map((row) => (
          <span
            key={row.key}
            className={row.tone}
            style={{ width: `${values[row.key] * 100}%` }}
          />
        ))}
      </div>
      <dl className={`grid gap-3 ${compact ? "grid-cols-3" : "sm:grid-cols-3"}`}>
        {ROWS.map((row) => (
          <div key={row.key} className="rounded-xl bg-surface-elevated px-3 py-3">
            <dt className="text-[11px] uppercase tracking-[0.16em] text-faint">{row.label}</dt>
            <dd
              className={`mt-1 font-mono tabular text-foreground ${compact ? "text-sm" : "text-lg"}`}
            >
              {formatProbability(values[row.key])}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
