"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { InsightCard } from "@/components/domain/insight-card";
import { MatchCard } from "@/components/domain/match-card";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import { PredictionCard } from "@/components/domain/prediction-card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { formatProbability, formatSignedPercent } from "@/lib/format/numbers";
import { useDashboard } from "@/lib/query/hooks";
import { pageMeta } from "@/lib/navigation";

export function DashboardView() {
  const { scenario, sport } = useFilters();
  const query = useDashboard(scenario);
  const meta = pageMeta["/"];

  if (query.isLoading) {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <ErrorState
        description={query.error?.message ?? "Réponse mock indisponible."}
        onRetry={() => void query.refetch()}
      />
    );
  }

  const snapshot = query.data.data;
  const matches = snapshot.matches_today.filter(
    (match) => sport === "all" || match.sport === sport,
  );

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={meta.eyebrow}
        title={meta.title}
        description={`${meta.description} ${snapshot.headline}.`}
      />
      <section className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Matchs du jour"
          value={matches.length}
          hint="Événements mock du 9 septembre 2026"
        />
        <MetricCard
          label="Log loss"
          value={snapshot.model_health.log_loss ?? "Indisponible"}
          hint={snapshot.model_health.model_version}
          tone="ai"
        />
        <MetricCard
          label="ROI théorique"
          value={formatSignedPercent(snapshot.model_health.theoretical_roi)}
          hint="Backtest mock, pas un rendement promis"
          tone="value"
        />
      </section>
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Matchs du jour</h2>
        {matches.length === 0 ? (
          <EmptyState
            title="Aucun match pour ce filtre"
            description="Élargissez le sport ou changez le scénario mock."
          />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {matches.map((match) => (
              <MatchCard key={match.id} match={match} />
            ))}
          </div>
        )}
      </section>
      <section className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Picks publiés</h2>
          {snapshot.picks.length === 0 ? (
            <EmptyState title="Aucun pick" description="Aucun signal ne répond aux critères mock." />
          ) : (
            snapshot.picks.slice(0, 2).map((pick) => <PredictionCard key={pick.id} pick={pick} />)
          )}
        </div>
        <div className="space-y-4">
          <h2 className="text-lg font-medium">Notes d’analyste</h2>
          {snapshot.insights.map((insight) => (
            <InsightCard key={insight.id} insight={insight} />
          ))}
          <p className="text-xs text-faint">
            Accuracy mock {formatProbability(snapshot.model_health.accuracy)} · Brier{" "}
            {snapshot.model_health.brier_score ?? "indisponible"} · n=
            {snapshot.model_health.prediction_count}
          </p>
        </div>
      </section>
    </div>
  );
}
