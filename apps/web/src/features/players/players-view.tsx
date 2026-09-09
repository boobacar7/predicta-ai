"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { TeamLogo } from "@/components/domain/team-logo";
import { Input } from "@/components/ui/input";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { pageMeta } from "@/lib/navigation";
import { usePlayers } from "@/lib/query/hooks";
import Link from "next/link";
import { useState } from "react";

export function PlayersView() {
  const { sport } = useFilters();
  const [queryText, setQueryText] = useState("");
  const query = usePlayers({ sport, query: queryText });
  const meta = pageMeta["/players"];

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
        placeholder="Rechercher un joueur mock"
        aria-label="Rechercher un joueur"
      />
      {query.data.data.items.length === 0 ? (
        <EmptyState title="Aucun joueur" description="Aucun profil mock pour ce filtre." />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {query.data.data.items.map((player) => (
            <Link key={player.id} href={`/players/${player.id}`}>
              <Card className="transition-colors hover:border-border-strong">
                <CardBody className="flex items-center gap-3">
                  <TeamLogo name={player.name} abbreviation={player.name.slice(0, 2).toUpperCase()} />
                  <div>
                    <p className="font-medium">{player.name}</p>
                    <p className="text-xs text-muted">
                      {player.sport} · {player.position ?? "Poste indisponible"}
                    </p>
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
