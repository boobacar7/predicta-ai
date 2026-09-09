"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { TeamComparison } from "@/components/domain/team-comparison";
import { Unavailable } from "@/components/domain/unavailable";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { pageMeta } from "@/lib/navigation";
import { useMatch, useMatches } from "@/lib/query/hooks";
import Link from "next/link";

export function AnalyticsView() {
  const { sport, scenario } = useFilters();
  const list = useMatches({ sport, date: "2026-09-09" }, scenario);
  const liveId = list.data?.data.items.find((match) => match.status === "live")?.id;
  const live = useMatch(liveId ?? "", scenario);
  const meta = pageMeta["/analytics"];

  if (list.isLoading) return <CardSkeleton rows={6} />;
  if (list.isError || !list.data) {
    return <ErrorState description={list.error?.message ?? "Réponse mock indisponible."} onRetry={() => void list.refetch()} />;
  }

  const matches = list.data.data.items;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      {matches.length === 0 ? (
        <EmptyState
          title="Pas de statistiques à afficher"
          description="Les indicateurs avancés suivent les matchs du jour mock."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {liveId && live.data ? (
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle>
                  <Link href={`/matches/${live.data.data.id}`} className="hover:text-ai-strong">
                    Live · {live.data.data.home.name} · {live.data.data.away.name}
                  </Link>
                </CardTitle>
              </CardHeader>
              <CardBody>
                <TeamComparison
                  home={live.data.data.home}
                  away={live.data.data.away}
                  stats={live.data.data.stats}
                />
              </CardBody>
            </Card>
          ) : null}
          {matches.map((match) => (
            <Card key={match.id}>
              <CardHeader>
                <CardTitle>
                  <Link href={`/matches/${match.id}`} className="hover:text-ai-strong">
                    {match.home.name} · {match.away.name}
                  </Link>
                </CardTitle>
              </CardHeader>
              <CardBody>
                {match.status === "live" ? (
                  <p className="text-sm text-muted">
                    Indicateurs live ci-dessus. xG reste indisponible s’il n’est pas dans le fact pack.
                  </p>
                ) : (
                  <Unavailable
                    label="Indicateurs avancés"
                    reason="Pas de statistiques pré-match détaillées dans ce jeu mock."
                  />
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
