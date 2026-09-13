"use client";

import { PageHeader } from "@/components/domain/page-header";
import { PrototypeNotice } from "@/components/domain/prototype-notice";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { TeamComparison } from "@/components/domain/team-comparison";
import { Unavailable } from "@/components/domain/unavailable";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { formatKickoff } from "@/lib/format/dates";
import { matchStatusLabels } from "@/lib/format/labels";
import { pageMeta } from "@/lib/navigation";
import { useMatch, useMatches } from "@/lib/query/hooks";
import type { MatchSummary } from "@/types/api";
import { isHistoricalMatchIdentity } from "@/types/api";
import Link from "next/link";

const meta = pageMeta["/analytics"];

export function AnalyticsView() {
  const { sport } = useFilters();
  const list = useMatches({ sport });

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <PrototypeNotice>
        Les statistiques de cette page suivent le catalogue de navigation. Aucun indicateur
        avancé du moteur football n&apos;est inventé ici.
      </PrototypeNotice>

      <QueryBoundary
        query={list}
        skeleton={<CardSkeleton rows={6} />}
        isEmpty={(result) => result.items.length === 0}
        empty={{
          title: "Pas de statistiques à afficher",
          description:
            "Les indicateurs avancés suivent les événements disponibles. Aucun n'est publié pour ce filtre.",
        }}
      >
        {(result) => {
          const detailed = result.items.find((match) => match.status === "live") ?? result.items[0];

          return (
            <div className="space-y-4">
              {detailed ? <DetailedComparison matchId={detailed.id} /> : null}

              <div className="grid gap-4 lg:grid-cols-2">
                {result.items
                  .filter((match) => match.id !== detailed?.id)
                  .map((match) => (
                    <SummaryCard key={match.id} match={match} />
                  ))}
              </div>
            </div>
          );
        }}
      </QueryBoundary>
    </div>
  );
}

/** Full statistic comparison for the most informative match of the selection. */
function DetailedComparison({ matchId }: { matchId: string }) {
  const query = useMatch(matchId);

  return (
    <QueryBoundary query={query} skeleton={<CardSkeleton rows={5} />}>
      {(match) =>
        isHistoricalMatchIdentity(match) ? (
          <Card>
            <CardBody>
              <Unavailable
                label="Comparaison statistique"
                reason="Cet identifiant ne renvoie qu'une identité structurelle archivée, sans statistiques."
              />
            </CardBody>
          </Card>
        ) : (
        <Card>
          <CardHeader>
            <CardTitle>
              <Link href={`/matches/${match.id}`} className="hover:text-ai-strong">
                {match.home.name} · {match.away.name}
              </Link>
            </CardTitle>
            <p className="text-xs text-faint">{matchStatusLabels[match.status]}</p>
          </CardHeader>
          <CardBody>
            {match.stats.length === 0 ? (
              <Unavailable
                label="Statistiques détaillées"
                reason="Aucun indicateur n'est publié pour cet événement."
              />
            ) : (
              <TeamComparison home={match.home} away={match.away} stats={match.stats} />
            )}
          </CardBody>
        </Card>
        )
      }
    </QueryBoundary>
  );
}

function SummaryCard({ match }: { match: MatchSummary }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <Link href={`/matches/${match.id}`} className="hover:text-ai-strong">
            {match.home.name} · {match.away.name}
          </Link>
        </CardTitle>
        <p className="text-xs text-faint">{formatKickoff(match.kickoff_at)}</p>
      </CardHeader>
      <CardBody>
        <Unavailable
          label="Indicateurs avancés"
          reason="Les statistiques détaillées ne sont exposées qu'à l'ouverture du match."
        />
      </CardBody>
    </Card>
  );
}
