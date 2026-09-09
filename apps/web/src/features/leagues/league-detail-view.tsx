"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { MatchCard } from "@/components/domain/match-card";
import { PageHeader } from "@/components/domain/page-header";
import { Unavailable } from "@/components/domain/unavailable";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useLeague } from "@/lib/query/hooks";

export function LeagueDetailView({ leagueId }: { leagueId: string }) {
  const query = useLeague(leagueId);

  if (query.isLoading) return <CardSkeleton rows={6} />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  const detail = query.data.data;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={detail.league.country}
        title={detail.league.name}
        description={`Saison ${detail.league.season}. Classement mock, non issu d'une compétition réelle.`}
      />
      {detail.unavailable_fields.length > 0 ? (
        <Unavailable
          label="Classement"
          reason={detail.unavailable_fields.map((field) => field.reason).join(" ")}
        />
      ) : (
        <Card>
          <CardBody>
            <table className="w-full text-sm">
              <caption className="sr-only">Classement mock {detail.league.name}</caption>
              <thead className="text-left text-xs uppercase tracking-[0.16em] text-faint">
                <tr>
                  <th className="py-2">Rang</th>
                  <th>Équipe</th>
                  <th>J</th>
                  <th>Pts</th>
                  <th>Diff</th>
                </tr>
              </thead>
              <tbody>
                {detail.standing.map((row) => (
                  <tr key={row.team.id} className="border-t border-border">
                    <td className="py-3 font-mono tabular">{row.rank ?? "—"}</td>
                    <td>{row.team.name}</td>
                    <td className="font-mono tabular">{row.played ?? "—"}</td>
                    <td className="font-mono tabular">{row.points ?? "—"}</td>
                    <td className="font-mono tabular">{row.goal_diff ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardBody>
        </Card>
      )}
      <section className="space-y-4">
        <h2 className="text-lg font-medium">Matchs récents</h2>
        {detail.recent_matches.length === 0 ? (
          <EmptyState title="Aucun match" description="Pas d'événement mock pour cette ligue." />
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
