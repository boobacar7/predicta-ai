"use client";

import { CalendarStrip } from "@/components/domain/calendar-strip";
import { LeagueFilter, StatusFilter } from "@/components/domain/filters";
import { MatchCard } from "@/components/domain/match-card";
import { PageHeader } from "@/components/domain/page-header";
import { PrototypeNotice } from "@/components/domain/prototype-notice";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Input } from "@/components/ui/input";
import { CardSkeleton } from "@/components/ui/skeleton";
import { searchMatches, upcomingDays } from "@/features/matches/selectors";
import { useFilters } from "@/lib/filters/context";
import { pageMeta } from "@/lib/navigation";
import { useLeagues, useMatches } from "@/lib/query/hooks";
import type { MatchStatus } from "@/types/api";
import { useDeferredValue, useState } from "react";

const meta = pageMeta["/matches"];
const days = upcomingDays(7);

export function MatchCenterView() {
  const { sport } = useFilters();
  const [date, setDate] = useState(days[0]);
  const [leagueId, setLeagueId] = useState("all");
  const [status, setStatus] = useState<MatchStatus | "all">("all");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);

  const leagues = useLeagues({ sport });
  const matches = useMatches({ sport, date, league_id: leagueId, status });

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <PrototypeNotice>
        Le Match Center est un catalogue de navigation. Un identifiant mth_* historique charge
        l&apos;identité canonique et le moteur football lorsqu&apos;ils existent.
      </PrototypeNotice>

      <CalendarStrip days={days} value={date} onChange={setDate} />

      <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-end">
        <LeagueFilter
          leagues={leagues.data?.data.items ?? []}
          value={leagueId}
          onChange={setLeagueId}
          disabled={leagues.isPending}
        />
        <StatusFilter value={status} onChange={setStatus} />
        <div className="md:ml-auto md:w-64">
          <Input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Rechercher une équipe"
            aria-label="Rechercher une équipe dans le calendrier"
          />
        </div>
      </div>

      <QueryBoundary
        query={matches}
        skeleton={
          <div className="grid gap-4 xl:grid-cols-2">
            <CardSkeleton rows={4} />
            <CardSkeleton rows={4} />
          </div>
        }
      >
        {(result) => {
          const items = searchMatches(result.items, deferredSearch);

          if (items.length === 0) {
            return (
              <p
                role="status"
                className="rounded-2xl border border-dashed border-border-strong px-6 py-16 text-center text-sm text-muted"
              >
                {result.items.length === 0
                  ? "Aucun événement ne correspond à cette date, ce sport, cette compétition ou ce statut."
                  : `Aucune équipe ne correspond à « ${deferredSearch.trim()} » parmi les ${result.items.length} événements de cette sélection.`}
              </p>
            );
          }

          return (
            <div className="grid gap-4 xl:grid-cols-2">
              {items.map((match) => (
                <MatchCard key={match.id} match={match} />
              ))}
            </div>
          );
        }}
      </QueryBoundary>
    </div>
  );
}
