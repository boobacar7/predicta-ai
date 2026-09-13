"use client";

import { AiPickCard } from "@/components/domain/ai-pick-card";
import { CandidateModelNotice } from "@/components/domain/model-status";
import { DataModeNotice } from "@/components/domain/data-mode-notice";
import { EmptyState } from "@/components/domain/empty-state";
import { MatchCard } from "@/components/domain/match-card";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import { PrototypeNotice } from "@/components/domain/prototype-notice";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Unavailable } from "@/components/domain/unavailable";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { footballValueRows } from "@/lib/football/value-rows";
import { FOOTBALL_PATHS, P1_SPORT } from "@/lib/football/routes";
import { football1x2Labels } from "@/lib/format/labels";
import { formatCount, formatPoints, formatSignedPercent, NO_VALUE_LABEL, UNAVAILABLE_LABEL } from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { useFootballAiPicks, useFootballValue, useMatches } from "@/lib/query/hooks";
import Link from "next/link";

const meta = pageMeta[FOOTBALL_PATHS.dashboard];

export function DashboardView() {
  const catalogue = useMatches({ sport: P1_SPORT });
  const picks = useFootballAiPicks({ limit: 2 });
  const valueMatchId = picks.data?.data.items[0]?.match_id ?? "";
  const value = useFootballValue(valueMatchId);

  return (
    <div className="space-y-8">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <section aria-label="Résumé de la journée" className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Matchs du jour"
          value={catalogue.isPending ? NO_VALUE_LABEL : formatCount(catalogue.data?.data.items.length ?? null)}
          hint="Catalogue de navigation football, pas le moteur"
        />
        <MetricCard
          label="Log loss"
          value={UNAVAILABLE_LABEL}
          hint="Métrique de performance du modèle candidat non publiée"
          tone="ai"
        />
        <MetricCard
          label="ROI théorique"
          value={UNAVAILABLE_LABEL}
          hint="Pas encore disponible via une API football stable"
          tone="value"
        />
      </section>

      {picks.data?.data.items[0] ? (
        <CandidateModelNotice
          version={picks.data.data.items[0].model_version}
          status={picks.data.data.items[0].model_status}
        />
      ) : null}

      <section className="space-y-4">
        <SectionHeading
          title="Matchs du jour"
          href={FOOTBALL_PATHS.matches}
          linkLabel="Tout le calendrier"
        />
        <PrototypeNotice>
          Le calendrier reste un catalogue de navigation. Les identifiants et probabilités fb-ens-*
          ne sont pas le moteur football-elo-v1-candidate.
        </PrototypeNotice>
        <QueryBoundary
          query={catalogue}
          skeleton={
            <div className="grid gap-4 xl:grid-cols-2">
              <CardSkeleton />
              <CardSkeleton />
            </div>
          }
          isEmpty={(result) => result.items.length === 0}
          empty={{
            title: "Aucun match pour ce filtre",
            description: "Consultez une autre date dans le Match Center.",
          }}
        >
          {(result) => (
            <div className="grid gap-4 xl:grid-cols-2">
              {result.items.map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </div>
          )}
        </QueryBoundary>
      </section>

      <div className="grid gap-8 lg:grid-cols-2">
        <section className="space-y-4">
          <SectionHeading title="AI Picks" href={FOOTBALL_PATHS.aiPicks} linkLabel="Tous les picks" />
          <QueryBoundary
            query={picks}
            skeleton={<CardSkeleton rows={4} />}
            isEmpty={(result) => result.items.length === 0}
            empty={{
              title: "Aucun pick publié",
              description: "Aucun signal ne satisfait les critères documentés pour le football.",
            }}
          >
            {(result, envelope) => (
              <div className="space-y-4">
                <DataModeNotice dataMode={envelope.data_mode} />
                {result.items.slice(0, 2).map((pick) => (
                  <AiPickCard key={`${pick.match_id}-${pick.selection}`} pick={pick} />
                ))}
              </div>
            )}
          </QueryBoundary>
        </section>

        <section className="space-y-4">
          <SectionHeading
            title="Value Finder"
            href={FOOTBALL_PATHS.value}
            linkLabel="Toutes les issues"
          />
          {valueMatchId ? (
            <QueryBoundary query={value} skeleton={<CardSkeleton rows={4} />}>
              {(analysis, envelope) => (
                <div className="space-y-3">
                  <DataModeNotice
                    dataMode={envelope.data_mode}
                    source={analysis.metadata.odds_source}
                  />
                  <p className="text-xs text-muted">
                    Analyse {analysis.match_id}. Cette donnée est informative et ne constitue pas
                    une recommandation.
                  </p>
                  {footballValueRows(analysis).map((row) => (
                    <Card key={row.selection}>
                      <CardBody className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-sm">
                          {football1x2Labels[row.selection]}
                          <span className="ml-2 font-mono text-xs text-faint">{row.selection}</span>
                        </p>
                        <dl className="flex gap-4">
                          <StatTile label="Edge" value={formatPoints(row.edge)} />
                          <StatTile label="EV" value={formatSignedPercent(row.ev)} tone="value" />
                        </dl>
                      </CardBody>
                    </Card>
                  ))}
                </div>
              )}
            </QueryBoundary>
          ) : picks.isPending ? (
            <CardSkeleton rows={4} />
          ) : (
            <EmptyState
              title="Aucune analyse de valeur"
              description="Aucun match football n'est encore publié pour le Value Engine."
            />
          )}
        </section>
      </div>

      <section className="space-y-4">
        <h2 className="text-lg font-medium">Performance des modèles</h2>
        <Unavailable
          label="Métriques de performance"
          reason="Aucune API stable ne publie encore le log loss, le Brier ou le ROI du modèle candidat football-elo-v1-candidate."
        />
      </section>
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
