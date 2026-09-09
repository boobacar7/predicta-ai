"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { MatchCard } from "@/components/domain/match-card";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import { Unavailable } from "@/components/domain/unavailable";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useTeam } from "@/lib/query/hooks";

export function TeamDetailView({ teamId }: { teamId: string }) {
  const query = useTeam(teamId);

  if (query.isLoading) return <CardSkeleton rows={6} />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  const detail = query.data.data;
  const elo = detail.stats.find((stat) => stat.key === "elo");
  const injuries = detail.stats.find((stat) => stat.key === "injuries");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={detail.league.name}
        title={detail.team.name}
        description="Profil mock. Les blessures et compositions réelles ne sont jamais inventées."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <MetricCard
          label="Elo mock"
          value={elo?.value ?? "Indisponible"}
          hint={elo?.quality.note ?? undefined}
          tone="ai"
        />
        {injuries?.quality.availability === "unavailable" ? (
          <Unavailable label="Blessures" reason="Non fournies par le jeu mock." />
        ) : (
          <MetricCard label="Blessures" value={injuries?.value ?? "Indisponible"} />
        )}
      </div>
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Matchs</h2>
        {detail.recent_matches.length === 0 ? (
          <EmptyState title="Aucun match" description="Cette équipe n'a pas d'événement mock." />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {detail.recent_matches.map((match) => (
              <MatchCard key={match.id} match={match} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
