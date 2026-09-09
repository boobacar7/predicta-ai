"use client";

import { CalendarStrip } from "@/components/domain/calendar-strip";
import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { LeagueFilter } from "@/components/domain/filters";
import { MatchCard } from "@/components/domain/match-card";
import { PageHeader } from "@/components/domain/page-header";
import { CardSkeleton } from "@/components/ui/skeleton";
import { isoDaysFromNow } from "@/data/mock/clock";
import { useFilters } from "@/lib/filters/context";
import { useLeagues, useMatches } from "@/lib/query/hooks";
import { pageMeta } from "@/lib/navigation";
import { useMemo, useState } from "react";

const days = [0, 1, 2, 3, 4, 5, 6].map((offset) => isoDaysFromNow(offset).slice(0, 10));

export function MatchCenterView() {
  const { sport, scenario } = useFilters();
  const [date, setDate] = useState(days[0] ?? "2026-09-09");
  const [leagueId, setLeagueId] = useState("all");
  const meta = pageMeta["/matches"];
  const leagues = useLeagues({ sport });
  const matches = useMatches(
    { sport, date, league_id: leagueId },
    scenario,
  );

  const leagueOptions = useMemo(
    () => leagues.data?.data.items ?? [],
    [leagues.data],
  );

  if (matches.isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <CardSkeleton rows={4} />
      </div>
    );
  }

  if (matches.isError || !matches.data) {
    return (
      <ErrorState description={matches.error?.message ?? "Réponse mock indisponible."} onRetry={() => void matches.refetch()} />
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <CalendarStrip days={days} value={date} onChange={setDate} />
      <LeagueFilter leagues={leagueOptions} value={leagueId} onChange={setLeagueId} />
      {matches.data.data.items.length === 0 ? (
        <EmptyState
          title="Aucun événement"
          description="Aucun match mock ne correspond à cette date, ce sport ou cette compétition."
        />
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {matches.data.data.items.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  );
}
