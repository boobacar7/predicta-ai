import { CandidateModelNotice, ModelStatusBadge } from "@/components/domain/model-status";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import {
  footballValueRows,
  sortFootballValueRows,
  type FootballValueSort,
} from "@/lib/football/value-rows";
import { football1x2Labels } from "@/lib/format/labels";
import {
  formatDecimalOdds,
  formatMetric,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import type { FootballValueAnalysis } from "@/types/api";

/**
 * Displays `GET /football/value/{match_id}` as published.
 *
 * Optional `sort` only reorders already-published rows.
 */
export function FootballValuePanel({
  analysis,
  sort = "selection",
}: {
  analysis: FootballValueAnalysis;
  sort?: FootballValueSort;
}) {
  const rows = sortFootballValueRows(footballValueRows(analysis), sort);

  return (
    <section className="space-y-4" aria-labelledby="football-value-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="football-value-heading" className="text-lg font-medium">
          Information de valeur
        </h2>
        <ModelStatusBadge
          version={analysis.metadata.model_version}
          status={analysis.metadata.model_status}
        />
      </div>

      <CandidateModelNotice
        version={analysis.metadata.model_version}
        status={analysis.metadata.model_status}
      />

      <p className="text-xs text-muted">
        Cette donnée est informative et ne constitue pas une recommandation. Les
        trois issues 1X2 sont affichées telles que le Value Engine les a publiées.
      </p>

      <ul className="grid gap-3">
        {rows.map((row) => (
          <li key={row.selection}>
            <Card>
              <CardBody className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">
                    {football1x2Labels[row.selection]}
                    <span className="ml-2 font-mono text-xs text-faint">{row.selection}</span>
                  </p>
                  <Badge tone="muted">{analysis.market}</Badge>
                </div>
                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                  <StatTile label="P modèle" value={formatProbability(row.model_probability)} />
                  <StatTile label="Cote" value={formatDecimalOdds(row.odds)} />
                  <StatTile label="Implicite" value={formatProbability(row.implied_probability)} />
                  <StatTile label="No-vig" value={formatProbability(row.no_vig_probability)} />
                  <StatTile label="Edge" value={formatPoints(row.edge)} tone="value" />
                  <StatTile label="EV" value={formatSignedPercent(row.ev)} tone="value" />
                </dl>
              </CardBody>
            </Card>
          </li>
        ))}
      </ul>

      <p className="text-xs text-faint">
        Overround (somme des implicites) {formatMetric(analysis.market_probabilities.overround)} ·{" "}
        <span className="font-mono">{analysis.metadata.value_engine_version}</span> · source{" "}
        <span className="font-mono">{analysis.metadata.odds_source}</span>
      </p>
    </section>
  );
}
