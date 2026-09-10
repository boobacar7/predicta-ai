"use client";

import { EmptyState } from "@/components/domain/empty-state";
import { InsightCard } from "@/components/domain/insight-card";
import { MatchCard } from "@/components/domain/match-card";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import { PredictionCard } from "@/components/domain/prediction-card";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { ValueBadge } from "@/components/domain/value-badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import { CardSkeleton } from "@/components/ui/skeleton";
import { selectDashboard, type FreshnessSummary } from "@/features/dashboard/selectors";
import { useFilters } from "@/lib/filters/context";
import { formatAbsolute } from "@/lib/format/dates";
import { availabilityLabels } from "@/lib/format/labels";
import {
  formatCount,
  formatMetric,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { useDashboard } from "@/lib/query/hooks";
import Link from "next/link";

const meta = pageMeta["/"];

export function DashboardView() {
  const { sport } = useFilters();
  const query = useDashboard();

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <QueryBoundary
        query={query}
        skeleton={
          <div className="grid gap-4 md:grid-cols-3">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        }
      >
        {(snapshot, envelope) => {
          const view = selectDashboard(snapshot, sport);

          return (
            <div className="space-y-8">
              <p className="text-sm text-muted">{view.headline}.</p>

              <section aria-label="Résumé de la journée" className="grid gap-4 md:grid-cols-3">
                <MetricCard
                  label="Matchs du jour"
                  value={formatCount(view.matches.length)}
                  hint="Événements correspondant au filtre sport"
                />
                <MetricCard
                  label="Log loss"
                  value={formatMetric(view.modelHealth.log_loss)}
                  hint={view.modelHealth.model_version}
                  tone="ai"
                />
                <MetricCard
                  label="ROI théorique"
                  value={formatSignedPercent(view.modelHealth.theoretical_roi)}
                  hint="Backtest, pas un rendement promis"
                  tone="value"
                />
              </section>

              <FreshnessPanel freshness={view.freshness} generatedAt={envelope.generated_at} />

              <section className="space-y-4">
                <SectionHeading title="Matchs du jour" href="/matches" linkLabel="Tout le calendrier" />
                {view.matches.length === 0 ? (
                  <EmptyState
                    title="Aucun match pour ce filtre"
                    description="Élargissez le filtre sport ou consultez une autre date dans le Match Center."
                  />
                ) : (
                  <div className="grid gap-4 xl:grid-cols-2">
                    {view.matches.map((match) => (
                      <MatchCard key={match.id} match={match} />
                    ))}
                  </div>
                )}
              </section>

              <div className="grid gap-8 lg:grid-cols-2">
                <section className="space-y-4">
                  <SectionHeading title="AI Picks" href="/ai-picks" linkLabel="Tous les picks" />
                  {view.picks.length === 0 ? (
                    <EmptyState
                      title="Aucun pick publié"
                      description="Aucun signal ne satisfait les critères documentés pour ce filtre."
                    />
                  ) : (
                    view.picks
                      .slice(0, 2)
                      .map((pick) => <PredictionCard key={pick.id} pick={pick} />)
                  )}
                </section>

                <section className="space-y-4">
                  <SectionHeading title="Value Finder" href="/value-finder" linkLabel="Tous les écarts" />
                  {view.valueOpportunities.length === 0 ? (
                    <EmptyState
                      title="Aucun écart publié"
                      description="Aucune cote exploitable n'est associée à une probabilité calibrée."
                    />
                  ) : (
                    view.valueOpportunities.slice(0, 2).map((item) => (
                      <Card key={item.id}>
                        <CardBody className="space-y-3">
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="text-xs text-faint">{item.match.league.name}</p>
                              <p className="truncate text-sm font-medium">
                                {item.match.home.name} · {item.match.away.name}
                              </p>
                              <p className="text-xs text-muted">{item.selection_label}</p>
                            </div>
                            <ValueBadge
                              preview={{
                                selection: item.selection,
                                edge: item.edge_no_vig,
                                expected_value: item.expected_value,
                                formula_version: item.formula_version,
                                quality: item.quality,
                              }}
                            />
                          </div>
                        </CardBody>
                      </Card>
                    ))
                  )}
                </section>
              </div>

              <section className="grid gap-8 lg:grid-cols-2">
                <div className="space-y-4">
                  <h2 className="text-lg font-medium">Notes d&apos;analyste</h2>
                  {view.insights.length === 0 ? (
                    <EmptyState
                      title="Aucune note"
                      description="Aucune note méthodologique n'accompagne cette journée."
                    />
                  ) : (
                    view.insights.map((insight) => (
                      <InsightCard key={insight.id} insight={insight} />
                    ))
                  )}
                </div>

                <div className="space-y-4">
                  <SectionHeading
                    title="Performance des modèles"
                    href="/performance"
                    linkLabel="Détail et calibration"
                  />
                  <Card>
                    <CardBody>
                      <dl className="grid grid-cols-2 gap-3">
                        <StatTile
                          label="Accuracy"
                          value={formatProbability(view.modelHealth.accuracy)}
                        />
                        <StatTile label="Brier" value={formatMetric(view.modelHealth.brier_score)} />
                        <StatTile label="ECE" value={formatMetric(view.modelHealth.ece)} />
                        <StatTile
                          label="Prédictions"
                          value={formatCount(view.modelHealth.prediction_count)}
                        />
                      </dl>
                      <p className="mt-3 text-xs text-faint">
                        {view.modelHealth.window_label} · {view.modelHealth.model_version}
                      </p>
                    </CardBody>
                  </Card>
                </div>
              </section>
            </div>
          );
        }}
      </QueryBoundary>
    </div>
  );
}

function SectionHeading({
  title,
  href,
  linkLabel,
}: {
  title: string;
  href: string;
  linkLabel: string;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-2">
      <h2 className="text-lg font-medium">{title}</h2>
      <Link href={href} className="text-xs text-ai-strong hover:underline">
        {linkLabel}
      </Link>
    </div>
  );
}

/** Availability breakdown of the day's payload, so gaps are visible up front. */
function FreshnessPanel({
  freshness,
  generatedAt,
}: {
  freshness: FreshnessSummary;
  generatedAt: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Fraîcheur des données</CardTitle>
        <p className="text-xs text-faint">Instantané généré le {formatAbsolute(generatedAt)}</p>
      </CardHeader>
      <CardBody>
        {freshness.total === 0 ? (
          <p className="text-sm text-muted">
            Aucun événement à évaluer pour ce filtre. Aucune complétude n&apos;est estimée.
          </p>
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile
                label={availabilityLabels.available}
                value={formatCount(freshness.counts.available)}
              />
              <StatTile
                label={availabilityLabels.partial}
                value={formatCount(freshness.counts.partial)}
              />
              <StatTile
                label={availabilityLabels.stale}
                value={formatCount(freshness.counts.stale)}
              />
              <StatTile
                label={availabilityLabels.unavailable}
                value={formatCount(freshness.counts.unavailable)}
              />
            </dl>
            <p className="mt-3 text-xs text-faint">
              {freshness.degraded
                ? "Une partie des événements du jour est partielle ou périmée. Les valeurs concernées restent signalées individuellement."
                : `Les ${formatCount(freshness.total)} événements du jour sont annoncés disponibles par la source.`}
            </p>
          </>
        )}
      </CardBody>
    </Card>
  );
}
