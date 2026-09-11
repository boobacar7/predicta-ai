import { ModelFavoriteBadge } from "@/components/domain/model-favorite-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import { selectionSideLabel } from "@/features/ai-analyst/format";
import { UNKNOWN_IDENTITY_LABEL } from "@/lib/format/identity";
import {
  formatDecimalOdds,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import type { FootballAiAnalystReport } from "@/types/api";

/**
 * Visual split between the model favorite and the highest-EV selection.
 *
 * `value.value_selection` is informational. It is never labelled as a pick,
 * a bet, or a recommendation. The published ratios belong to `value.selection`
 * (the favorite), not to the best-EV side.
 */
export function ValueInformation({ report }: { report: FootballAiAnalystReport }) {
  const value = report.value;
  const available = value.availability === "available";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Information de valeur</CardTitle>
      </CardHeader>
      <CardBody className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <article className="rounded-xl border border-ai/25 bg-ai-soft px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-faint">Favori du modèle</p>
            <div className="mt-2">
              <ModelFavoriteBadge selection={report.model_favorite} />
            </div>
            <p className="mt-2 text-sm text-muted">
              Issue à la plus haute probabilité modèle. Ce n&apos;est pas une recommandation.
            </p>
          </article>

          <article className="rounded-xl border border-value/25 bg-value-soft px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-faint">Valeur détectée</p>
            <div className="mt-2">
              <Badge tone="value" aria-label={`Valeur détectée : ${selectionSideLabel(value.value_selection)}`}>
                Valeur détectée · {selectionSideLabel(value.value_selection)}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-muted">
              Issue au plus haut EV théorique publié. Cette donnée est informative et ne
              constitue pas une recommandation.
            </p>
          </article>
        </div>

        {available ? (
          <div>
            <p className="mb-2 text-xs text-faint">
              Mesures copiées pour le favori du modèle ({selectionSideLabel(value.selection)}), pas
              pour la valeur détectée.
            </p>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <StatTile label="Cote" value={formatDecimalOdds(value.odds)} />
              <StatTile label="Implicite" value={formatProbability(value.implied_probability)} />
              <StatTile label="No-vig" value={formatProbability(value.no_vig_probability)} />
              <StatTile label="Edge" value={formatPoints(value.edge)} tone="value" />
              <StatTile label="EV" value={formatSignedPercent(value.ev)} tone="value" />
              <StatTile
                label="Value Engine"
                value={value.value_engine_version ?? UNKNOWN_IDENTITY_LABEL}
              />
            </dl>
          </div>
        ) : (
          <p className="text-sm text-muted">
            Information indisponible — aucune analyse de valeur n&apos;est publiée pour ce cutoff.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
