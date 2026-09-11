"use client";

import { AIConfidence } from "@/components/domain/ai-confidence";
import { DataFreshness, Provenance } from "@/components/domain/data-freshness";
import { MatchTimeline } from "@/components/domain/match-timeline";
import { OddsDisplay } from "@/components/domain/odds-display";
import { PageHeader } from "@/components/domain/page-header";
import { ProbabilityBar } from "@/components/domain/probability-bar";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { TeamComparison } from "@/components/domain/team-comparison";
import { TeamLogo } from "@/components/domain/team-logo";
import { Unavailable } from "@/components/domain/unavailable";
import { ValueBadge } from "@/components/domain/value-badge";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { formatAbsolute, formatKickoff } from "@/lib/format/dates";
import { formatKickoffOrUnknown, formatMatchup } from "@/lib/format/identity";
import { matchStatusLabels, sportLabels } from "@/lib/format/labels";
import { formatPoints, formatScore } from "@/lib/format/numbers";
import { useMatch } from "@/lib/query/hooks";
import type { HistoricalMatchIdentity, MatchDetail } from "@/types/api";
import { isHistoricalMatchIdentity } from "@/types/api";
import Link from "next/link";

export function MatchDetailView({ matchId }: { matchId: string }) {
  const query = useMatch(matchId);

  return (
    <QueryBoundary
      query={query}
      skeleton={<CardSkeleton rows={8} />}
      quality={(match) => (isHistoricalMatchIdentity(match) ? null : match.quality)}
    >
      {(match) =>
        isHistoricalMatchIdentity(match) ? (
          <HistoricalIdentityContent identity={match} />
        ) : (
          <MatchDetailContent match={match} />
        )
      }
    </QueryBoundary>
  );
}

function MatchDetailContent({ match }: { match: MatchDetail }) {
  const showScore = match.status === "finished" || match.status === "live";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`${sportLabels[match.sport]} · ${match.league.name}`}
        title={`${match.home.name} · ${match.away.name}`}
        description={`${formatKickoff(match.kickoff_at)} · ${match.venue ?? "Lieu indisponible"}`}
        actions={<Badge tone="muted">{matchStatusLabels[match.status]}</Badge>}
      />

      <div className="flex flex-wrap items-center gap-3">
        <DataFreshness quality={match.quality} />
        <Provenance quality={match.quality} />
      </div>

      <div className="flex items-center justify-center gap-4 rounded-2xl border border-border bg-surface p-6 sm:gap-8">
        <TeamLogo name={match.home.name} abbreviation={match.home.abbreviation} size="lg" />
        {showScore ? (
          <p className="font-mono text-3xl tabular">
            {formatScore(match.score.home)} – {formatScore(match.score.away)}
          </p>
        ) : (
          <p className="text-xs uppercase tracking-[0.18em] text-faint">
            {formatKickoff(match.kickoff_at)}
          </p>
        )}
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
                  {match.value_preview ? <ValueBadge preview={match.value_preview} /> : null}
                </div>
                <ProbabilityBar outcomes={match.prediction.outcomes} />
                <p className="text-xs text-faint">
                  Cutoff des données {formatAbsolute(match.prediction.cutoff_at)} · calibrateur{" "}
                  {match.prediction.calibrator_version} · features{" "}
                  {match.prediction.feature_set_version}
                </p>
                <div>
                  <h3 className="text-sm font-medium">Facteurs explicatifs</h3>
                  <ul className="mt-2 space-y-2 text-sm text-muted">
                    {match.prediction.factors.map((factor) => (
                      <li key={factor.id}>
                        <span className="text-foreground">{factor.label}.</span> {factor.detail}
                        {factor.quality.availability === "unavailable" ? (
                          <span className="text-warning"> (donnée indisponible)</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
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
            {match.odds && match.odds.overround !== null ? (
              <p className="mt-3 text-xs text-faint">
                Overround estimé {formatPoints(match.odds.overround)}. Les probabilités no-vig sont
                calculées par le Value Engine, pas par l&apos;interface.
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
        <section className="space-y-2">
          <h2 className="text-sm font-medium">Données non fournies</h2>
          <div className="grid gap-2 md:grid-cols-2">
            {match.unavailable_fields.map((field) => (
              <Unavailable key={field.field} label={field.field} reason={field.reason} />
            ))}
          </div>
        </section>
      ) : null}

      <Link href={`/ai-analyst?match_id=${match.id}`} className="inline-block text-sm text-ai-strong hover:underline">
        Ouvrir dans l&apos;AI Analyst
      </Link>
    </div>
  );
}

/**
 * `GET /matches/{match_id}` answers with `HistoricalMatchIdentity` for ids that
 * exist in the point-in-time archive but have no projection in the frontend
 * repository — the ids the AI Picks engine works on.
 *
 * The payload is structural by construction: no score, no status, no timeline,
 * no statistics. Rendering it as a degraded `MatchDetail` would suggest those
 * sections merely failed to load, so the page states the scope instead.
 */
function HistoricalIdentityContent({ identity }: { identity: HistoricalMatchIdentity }) {
  const matchup = formatMatchup(identity.home_team, identity.away_team);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`Football · ${identity.league}`}
        title={matchup.text}
        description={formatKickoffOrUnknown(identity.kickoff_at)}
        actions={<Badge tone="muted">Identité archivée</Badge>}
      />

      <Card>
        <CardHeader>
          <CardTitle>Identité du match</CardTitle>
        </CardHeader>
        <CardBody className="space-y-3 text-sm">
          <dl className="grid gap-3 sm:grid-cols-2">
            <IdentityField label="Équipe à domicile" value={matchup.home} />
            <IdentityField label="Équipe à l'extérieur" value={matchup.away} />
            <IdentityField label="Compétition" value={identity.league} />
            <IdentityField label="Coup d'envoi" value={formatKickoffOrUnknown(identity.kickoff_at)} />
            <IdentityField label="Identifiant domicile" value={identity.home_team_id} mono />
            <IdentityField label="Identifiant extérieur" value={identity.away_team_id} mono />
          </dl>
        </CardBody>
      </Card>

      <Unavailable
        label="Statistiques, cotes, prédiction et chronologie"
        reason="Ce match n'est disponible que sous forme d'identité structurelle archivée ; aucune de ces sections n'est publiée pour cet identifiant."
      />
    </div>
  );
}

function IdentityField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.14em] text-faint">{label}</dt>
      <dd className={mono ? "mt-1 font-mono text-xs break-all text-muted" : "mt-1 text-foreground"}>
        {value}
      </dd>
    </div>
  );
}
