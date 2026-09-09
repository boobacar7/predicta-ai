"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { TeamLogo } from "@/components/domain/team-logo";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { pageMeta } from "@/lib/navigation";
import { useTeams } from "@/lib/query/hooks";
import Link from "next/link";
import { useState } from "react";

export function TeamsView() {
  const { sport } = useFilters();
  const [queryText, setQueryText] = useState("");
  const query = useTeams({ sport, query: queryText });
  const meta = pageMeta["/teams"];

  if (query.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <CardSkeleton />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <Input
        value={queryText}
        onChange={(event) => setQueryText(event.target.value)}
        placeholder="Rechercher une équipe mock"
        aria-label="Rechercher une équipe"
      />
      {query.data.data.items.length === 0 ? (
        <EmptyState title="Aucune équipe" description="Aucun club mock ne correspond à ce filtre." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {query.data.data.items.map((team) => (
            <Link key={team.id} href={`/teams/${team.id}`}>
              <Card className="transition-colors hover:border-border-strong">
                <CardBody className="flex items-center gap-3">
                  <TeamLogo name={team.name} abbreviation={team.abbreviation} />
                  <div>
                    <p className="font-medium">{team.name}</p>
                    <p className="text-xs text-muted">{team.sport}</p>
                  </div>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
