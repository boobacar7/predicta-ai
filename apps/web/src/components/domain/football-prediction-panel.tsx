import { CandidateModelNotice, ModelStatusBadge } from "@/components/domain/model-status";
import { formatAbsolute } from "@/lib/format/dates";
import { formatProbability } from "@/lib/format/numbers";
import type { FootballModelPrediction } from "@/types/api";

const ROWS = [
  { key: "HOME" as const, label: "HOME", tone: "bg-home" },
  { key: "DRAW" as const, label: "DRAW", tone: "bg-draw" },
  { key: "AWAY" as const, label: "AWAY", tone: "bg-away" },
];

/**
 * Displays `GET /football/predictions/{match_id}` as published.
 *
 * No favorite is inferred: that label exists only on the AI Analyst report.
 */
export function FootballPredictionPanel({ prediction }: { prediction: FootballModelPrediction }) {
  const values = {
    HOME: prediction.home_probability,
    DRAW: prediction.draw_probability,
    AWAY: prediction.away_probability,
  };

  return (
    <section className="space-y-4" aria-labelledby="football-prediction-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="football-prediction-heading" className="text-lg font-medium">
          Prédiction moteur
        </h2>
        <ModelStatusBadge version={prediction.model_version} status={prediction.model_status} />
      </div>

      <CandidateModelNotice version={prediction.model_version} status={prediction.model_status} />

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
        <dl className="grid gap-3 sm:grid-cols-3">
          {ROWS.map((row) => (
            <div key={row.key} className="rounded-xl bg-surface-elevated px-3 py-3">
              <dt className="text-[11px] uppercase tracking-[0.16em] text-faint">{row.label}</dt>
              <dd className="mt-1 font-mono text-lg tabular text-foreground">
                {formatProbability(values[row.key])}
              </dd>
            </div>
          ))}
        </dl>
      </div>

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
    </section>
  );
}
