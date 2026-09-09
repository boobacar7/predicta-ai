"use client";

import { EmptyState } from "@/components/domain/empty-state";
import { MatchCard } from "@/components/domain/match-card";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Unavailable } from "@/components/domain/unavailable";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { sportLabels } from "@/lib/format/labels";
import { formatCount, formatNumber } from "@/lib/format/numbers";
import { useLeague } from "@/lib/query/hooks";
import type { StandingRow } from "@/types/api";

export function LeagueDetailView({ leagueId }: { leagueId: string }) {
  const query = useLeague(leagueId);

  return (
    <QueryBoundary query={query} skeleton={<CardSkeleton rows={6} />}>
      {(detail) => (
        <div className="space-y-6">
          <PageHeader
            eyebrow={`${sportLabels[detail.league.sport]} · ${detail.league.country}`}
            title={detail.league.name}
            description={`Saison ${detail.league.season}.`}
          />

          {detail.unavailable_fields.map((field) => (
            <Unavailable key={field.field} label={field.field} reason={field.reason} />
          ))}

          {detail.standing.length > 0 ? (
            <section className="space-y-3">
              <h2 className="text-lg font-medium">Classement</h2>
              <StandingTable leagueName={detail.league.name} rows={detail.standing} />
            </section>
          ) : null}

          <section className="space-y-4">
            <h2 className="text-lg font-medium">Matchs récents</h2>
            {detail.recent_matches.length === 0 ? (
              <EmptyState
                title="Aucun match"
                description="Aucun événement n'est référencé pour cette compétition."
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

function StandingTable({ leagueName, rows }: { leagueName: string; rows: StandingRow[] }) {
  return (
    <Card>
      <CardBody className="overflow-x-auto p-0">
        <table className="w-full min-w-[32rem] text-sm">
          <caption className="sr-only">Classement de {leagueName}</caption>
          <thead className="text-left text-xs uppercase tracking-[0.16em] text-faint">
            <tr className="border-b border-border">
              <th scope="col" className="px-5 py-3">
                Rang
              </th>
              <th scope="col" className="py-3">
                Équipe
              </th>
              <th scope="col" className="py-3 text-right">
                J
              </th>
              <th scope="col" className="py-3 text-right">
                Pts
              </th>
              <th scope="col" className="px-5 py-3 text-right">
                Diff
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.team.id} className="border-t border-border">
                <td className="px-5 py-3 font-mono tabular">{formatNumber(row.rank)}</td>
                <th scope="row" className="py-3 text-left font-normal">
                  {row.team.name}
                </th>
                <td className="py-3 text-right font-mono tabular">{formatCount(row.played)}</td>
                <td className="py-3 text-right font-mono tabular">{formatCount(row.points)}</td>
                <td className="px-5 py-3 text-right font-mono tabular">
                  {formatNumber(row.goal_diff)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
