"use client";

import { EmptyState } from "@/components/domain/empty-state";
import { MatchCard } from "@/components/domain/match-card";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { StatGrid } from "@/components/domain/stat-grid";
import { TeamLogo } from "@/components/domain/team-logo";
import { Unavailable } from "@/components/domain/unavailable";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useTeam } from "@/lib/query/hooks";

export function TeamDetailView({ teamId }: { teamId: string }) {
  const query = useTeam(teamId);

  return (
    <QueryBoundary query={query} skeleton={<CardSkeleton rows={6} />}>
      {(detail) => (
        <div className="space-y-6">
          <PageHeader
            eyebrow={detail.league.name}
            title={detail.team.name}
            description={`${detail.team.short_name} · ${detail.team.abbreviation}`}
            actions={
              <TeamLogo
                name={detail.team.name}
                abbreviation={detail.team.abbreviation}
                size="lg"
              />
            }
          />

          <StatGrid stats={detail.stats} />

          {detail.unavailable_fields.length > 0 ? (
            <div className="grid gap-2 md:grid-cols-2">
              {detail.unavailable_fields.map((field) => (
                <Unavailable key={field.field} label={field.field} reason={field.reason} />
              ))}
            </div>
          ) : null}

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Matchs</h2>
            {detail.recent_matches.length === 0 ? (
              <EmptyState
                title="Aucun match"
                description="Aucun événement n'est référencé pour cette équipe."
              />
            ) : (
              <div className="grid gap-4 xl:grid-cols-2">
                {detail.recent_matches.map((match) => (
                  <MatchCard key={match.id} match={match} />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </QueryBoundary>
  );
}
