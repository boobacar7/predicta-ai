"use client";

import { DataModeNotice } from "@/components/domain/data-mode-notice";
import { EmptyState } from "@/components/domain/empty-state";
import { SelectFilter } from "@/components/domain/filters";
import { FootballValuePanel } from "@/components/domain/football-value-panel";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { DialogContent, DialogRoot, DialogTrigger } from "@/components/ui/dialog";
import { CardSkeleton } from "@/components/ui/skeleton";
import { type FootballValueSort } from "@/features/value/selectors";
import { isDataSourceError } from "@/lib/api/errors";
import { footballMatchOptions } from "@/lib/football/match-options";
import { FOOTBALL_PATHS, P1_SPORT, footballAnalystPath, footballMatchPath } from "@/lib/football/routes";
import { useFootballMatchId } from "@/lib/football/use-match-id";
import { formatMatchup } from "@/lib/format/identity";
import { pageMeta } from "@/lib/navigation";
import { useFootballAiPicks, useFootballValue, useMatch, useMatches } from "@/lib/query/hooks";
import { isHistoricalMatchIdentity } from "@/types/api";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

const meta = pageMeta[FOOTBALL_PATHS.value];

const sortOptions: Array<{ value: FootballValueSort; label: string }> = [
  { value: "selection", label: "HOME / DRAW / AWAY" },
  { value: "edge", label: "Edge" },
  { value: "ev", label: "EV" },
  { value: "probability", label: "Probabilité modèle" },
  { value: "odds", label: "Cote" },
];

/**
 * Value Finder, backed by `GET /football/value/{match_id}`.
 *
 * The contract has no list route. The page inspects one match at a time and
 * copies the three 1X2 rows the Value Engine already calculated. Local sort
 * only reorders those rows.
 */
export function ValueFinderView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { matchId, pending } = useFootballMatchId();
  const [sort, setSort] = useState<FootballValueSort>("selection");

  const query = useFootballValue(matchId);
  const identityQuery = useMatch(matchId);
  const matches = useMatches({ sport: P1_SPORT });
  const picks = useFootballAiPicks({ limit: 50 });

  const options = useMemo(
    () =>
      footballMatchOptions({
        matches: matches.data?.data.items,
        picks: picks.data?.data.items,
        currentId: matchId,
      }),
    [matches.data?.data.items, picks.data?.data.items, matchId],
  );

  const onMatchChange = useCallback(
    (next: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("match_id", next);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  if (pending) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow={meta.eyebrow}
          title={meta.title}
          description={meta.description}
          actions={<FormulaDialog />}
        />
        <CardSkeleton rows={6} />
      </div>
    );
  }

  if (!matchId) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow={meta.eyebrow}
          title={meta.title}
          description={meta.description}
          actions={<FormulaDialog />}
        />
        <EmptyState
          title="Aucun match à évaluer"
          description="Le Value Engine n'a aucun identifiant football à afficher. Passez un match_id ou attendez une publication."
        />
      </div>
    );
  }

  if (query.isError && isDataSourceError(query.error) && query.error.kind === "not_found") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow={meta.eyebrow}
          title={meta.title}
          description={meta.description}
          actions={<FormulaDialog />}
        />
        <MatchPicker value={matchId} onChange={onMatchChange} options={options} />
        <EmptyState
          title="Aucune analyse de valeur"
          description="Le Value Engine n'a publié aucune analyse pour cet identifiant. Ce n'est pas une erreur masquée par des données mock."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={meta.eyebrow}
        title={meta.title}
        description={meta.description}
        actions={<FormulaDialog />}
      />

      <MatchPicker value={matchId} onChange={onMatchChange} options={options} />

      <QueryBoundary query={query} skeleton={<CardSkeleton rows={6} />}>
        {(analysis, envelope) => {
          const identity = identityQuery.data?.data;
          const matchup = !identity
            ? analysis.match_id
            : isHistoricalMatchIdentity(identity)
              ? formatMatchup(identity.home_team, identity.away_team).text
              : `${identity.home.name} vs ${identity.away.name}`;

          return (
            <div className="space-y-5">
              <DataModeNotice
                dataMode={envelope.data_mode}
                source={analysis.metadata.odds_source}
              />

              <Card>
                <CardBody className="space-y-1">
                  <p className="text-xs uppercase tracking-[0.16em] text-faint">Match évalué</p>
                  <p className="text-lg font-medium">{matchup}</p>
                  <p className="text-xs text-muted">
                    Identifiant <span className="font-mono">{analysis.match_id}</span>
                  </p>
                </CardBody>
              </Card>

              <section
                aria-label="Affinage local des issues"
                className="space-y-2 rounded-2xl border border-border bg-surface px-4 py-3"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-faint">
                  Affinage local · non supporté par{" "}
                  <span className="font-mono">GET /football/value/{"{match_id}"}</span>
                </p>
                <SelectFilter
                  label="Trier par"
                  value={sort}
                  onChange={(value) => setSort(value as FootballValueSort)}
                >
                  {sortOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </SelectFilter>
              </section>

              <FootballValuePanel analysis={analysis} sort={sort} />

              <Link
                href={footballMatchPath(analysis.match_id)}
                className="inline-block text-sm text-ai-strong hover:underline"
              >
                Voir le match
              </Link>
              <span className="mx-2 text-faint" aria-hidden="true">
                ·
              </span>
              <Link
                href={footballAnalystPath(analysis.match_id)}
                className="inline-block text-sm text-ai-strong hover:underline"
              >
                Ouvrir dans l&apos;AI Analyst
              </Link>
            </div>
          );
        }}
      </QueryBoundary>
    </div>
  );
}

function MatchPicker({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<{ id: string; label: string }>;
}) {
  return (
    <section
      aria-label="Match évalué"
      className="rounded-2xl border border-border bg-surface px-4 py-3"
    >
      <SelectFilter label="Match" value={value} onChange={onChange}>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </SelectFilter>
    </section>
  );
}

/** Documents the Value Engine formulas without recomputing them in the UI. */
function FormulaDialog() {
  return (
    <DialogRoot>
      <DialogTrigger asChild>
        <Button size="sm">Formules</Button>
      </DialogTrigger>
      <DialogContent title="Value Engine">
        <ul className="space-y-2 text-sm leading-6 text-muted">
          <li>Probabilité implicite brute = 1 / cote décimale</li>
          <li>Overround = somme des implicites brutes</li>
          <li>Probabilité no-vig = implicite_i / somme des implicites</li>
          <li>Edge = probabilité modèle − probabilité implicite brute</li>
          <li>EV = (probabilité modèle × cote décimale) − 1</li>
        </ul>
        <p className="mt-4 text-xs text-faint">
          Ces valeurs sont calculées et versionnées par{" "}
          <span className="font-mono">GET /football/value/{"{match_id}"}</span>. L&apos;interface
          les affiche telles quelles et ne recalcule aucune référence métier.
        </p>
      </DialogContent>
    </DialogRoot>
  );
}
