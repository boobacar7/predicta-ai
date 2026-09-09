"use client";

import { AIConfidence } from "@/components/domain/ai-confidence";
import { DataFreshness, Provenance } from "@/components/domain/data-freshness";
import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { MatchTimeline } from "@/components/domain/match-timeline";
import { OddsDisplay } from "@/components/domain/odds-display";
import { PageHeader } from "@/components/domain/page-header";
import { ProbabilityBar } from "@/components/domain/probability-bar";
import { TeamComparison } from "@/components/domain/team-comparison";
import { TeamLogo } from "@/components/domain/team-logo";
import { Unavailable } from "@/components/domain/unavailable";
import { ValueBadge } from "@/components/domain/value-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { formatKickoff } from "@/lib/format/dates";
import { matchStatusLabels, sportLabels } from "@/lib/format/labels";
import { useMatch } from "@/lib/query/hooks";
import Link from "next/link";

export function MatchDetailView({ matchId }: { matchId: string }) {
  const { scenario } = useFilters();
  const query = useMatch(matchId, scenario);

  if (query.isLoading) return <CardSkeleton rows={8} />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  const match = query.data.data;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={sportLabels[match.sport]}
        title={`${match.home.name} · ${match.away.name}`}
        description={`${match.league.name} · ${formatKickoff(match.kickoff_at)} · ${match.venue ?? "Lieu indisponible"}`}
        actions={<Badge tone="muted">{matchStatusLabels[match.status]}</Badge>}
      />
      <div className="flex flex-wrap items-center gap-3">
        <DataFreshness quality={match.quality} />
        <Provenance quality={match.quality} />
      </div>
      <div className="flex items-center justify-center gap-6 rounded-2xl border border-border bg-surface p-6">
        <TeamLogo name={match.home.name} abbreviation={match.home.abbreviation} size="lg" />
        <p className="font-mono text-3xl tabular">
          {match.score.home ?? "—"} – {match.score.away ?? "—"}
        </p>
        <TeamLogo name={match.away.name} abbreviation={match.away.abbreviation} size="lg" />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Probabilités calibrées</CardTitle>
          </CardHeader>
          <CardBody className="space-y-4">
            {match.prediction ? (
              <>
                <div className="flex flex-wrap gap-2">
                  <AIConfidence level={match.prediction.confidence} />
                  <Badge tone="ai">{match.prediction.model_version}</Badge>
                  <ValueBadge preview={match.value_preview} />
                </div>
                <ProbabilityBar outcomes={match.prediction.outcomes} />
                <p className="text-xs text-faint">
                  Cutoff {match.prediction.cutoff_at} · calibrateur {match.prediction.calibrator_version}
                </p>
                <ul className="space-y-2 text-sm text-muted">
                  {match.prediction.factors.map((factor) => (
                    <li key={factor.id}>
                      <span className="text-foreground">{factor.label}.</span> {factor.detail}
                      {factor.quality.availability === "unavailable" ? " (indisponible)" : ""}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <Unavailable
                label="Prédiction"
                reason="Aucune version de modèle n'est publiée pour ce match."
              />
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Cotes observées</CardTitle>
          </CardHeader>
          <CardBody>
            <OddsDisplay odds={match.odds} />
            {match.odds?.overround !== null && match.odds ? (
              <p className="mt-3 text-xs text-faint">
                Overround estimé {(match.odds.overround * 100).toFixed(1)} pts. Formule Value Engine
                0.1.
              </p>
            ) : null}
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Statistiques</CardTitle>
          </CardHeader>
          <CardBody>
            <TeamComparison home={match.home} away={match.away} stats={match.stats} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Chronologie</CardTitle>
          </CardHeader>
          <CardBody>
            <MatchTimeline events={match.timeline} />
          </CardBody>
        </Card>
      </div>
      {match.unavailable_fields.length > 0 ? (
        <EmptyState
          title="Données manquantes"
          description={match.unavailable_fields.map((field) => field.reason).join(" ")}
        />
      ) : null}
      <Link href="/analyst" className="text-sm text-ai-strong hover:underline">
        Ouvrir dans l’AI Analyst
      </Link>
    </div>
  );
}
