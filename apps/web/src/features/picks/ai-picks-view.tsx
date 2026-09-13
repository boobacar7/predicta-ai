"use client";

import { AiPickCard } from "@/components/domain/ai-pick-card";
import { AiPickDetailDialog } from "@/components/domain/ai-pick-detail";
import { DataModeNotice } from "@/components/domain/data-mode-notice";
import { ExclusionsPanel } from "@/components/domain/exclusions-panel";
import { DateFilter, SelectFilter, ThresholdFilter } from "@/components/domain/filters";
import { CandidateModelNotice } from "@/components/domain/model-status";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Button } from "@/components/ui/button";
import { CardSkeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { describePage, summarizeAiPicks } from "@/features/picks/selectors";
import { FOOTBALL_PATHS } from "@/lib/football/routes";
import { football1x2Labels } from "@/lib/format/labels";
import {
  formatCount,
  formatMetric,
  formatPoints,
  formatSignedPercent,
} from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { useFootballAiPicks } from "@/lib/query/hooks";
import type { AiPick, AiPicksResult } from "@/types/api";
import { useMemo, useState } from "react";

const meta = pageMeta[FOOTBALL_PATHS.aiPicks];
const PAGE_SIZE = 6;

/**
 * AI Picks, backed by `GET /football/ai-picks` (`ai-picks-0.1`).
 *
 * The view selects, formats and paginates. It derives no probability, edge,
 * expected value, score or rank: those are produced by the engine and rendered
 * as published, which is what keeps this page a presentation layer.
 *
 * Filtering happens server-side. Date, league and the two thresholds are query
 * parameters of the endpoint, so a threshold does not merely hide rows: it
 * makes the engine re-evaluate eligibility and report the rejected selections.
 */
export function AiPicksView() {
  const [date, setDate] = useState("");
  const [league, setLeague] = useState("all");
  const [minEdge, setMinEdge] = useState<number | null>(null);
  const [minEv, setMinEv] = useState<number | null>(null);
  const [page, setPage] = useState(0);
  const [detail, setDetail] = useState<AiPick | null>(null);

  const filters = useMemo(
    () => ({
      date: date || undefined,
      league: league === "all" ? undefined : league,
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
      min_edge: minEdge ?? undefined,
      min_ev: minEv ?? undefined,
    }),
    [date, league, minEdge, minEv, page],
  );

  const query = useFootballAiPicks(filters);

  // League options come from the unfiltered result for the same date, so the
  // list does not collapse to the single league already selected.
  const optionsQuery = useFootballAiPicks({ date: date || undefined, limit: 100 });
  const leagueOptions = useMemo(
    () => leaguesIn(optionsQuery.data?.data),
    [optionsQuery.data?.data],
  );

  const resetPage = <T,>(apply: (value: T) => void) => (value: T) => {
    apply(value);
    setPage(0);
  };

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <section
        aria-label="Filtres des opportunités"
        className="flex flex-wrap items-end gap-3 rounded-2xl border border-border bg-surface px-4 py-3"
      >
        <SelectFilter label="Sport" value="football" onChange={() => undefined} disabled>
          <option value="football">Football</option>
        </SelectFilter>

        <SelectFilter label="Compétition" value={league} onChange={resetPage(setLeague)}>
          <option value="all">Toutes</option>
          {leagueOptions.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </SelectFilter>

        <DateFilter value={date} onChange={resetPage(setDate)} />
        <ThresholdFilter label="Edge min" value={minEdge} onChange={resetPage(setMinEdge)} />
        <ThresholdFilter
          label="EV min"
          value={minEv}
          onChange={resetPage(setMinEv)}
          suffix="%"
          step={1}
        />

        {date || league !== "all" || minEdge !== null || minEv !== null ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setDate("");
              setLeague("all");
              setMinEdge(null);
              setMinEv(null);
              setPage(0);
            }}
          >
            Réinitialiser
          </Button>
        ) : null}
      </section>

      <QueryBoundary
        query={query}
        skeleton={
          <div className="space-y-4">
            <CardSkeleton rows={2} />
            <div className="grid gap-4 lg:grid-cols-2">
              <CardSkeleton rows={5} />
              <CardSkeleton rows={5} />
            </div>
          </div>
        }
      >
        {(result, envelope) => {
          const summary = summarizeAiPicks(result.items, result.total);
          const pageInfo = describePage(result.total, result.limit, result.offset);
          const model = result.items[0];

          return (
            <div className="space-y-5">
              <DataModeNotice dataMode={envelope.data_mode} source={model?.odds_source} />
              {model ? (
                <CandidateModelNotice
                  version={model.model_version}
                  status={model.model_status}
                />
              ) : null}

              <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <StatTile
                  label="Opportunités"
                  value={formatCount(summary.total)}
                  hint={`${formatCount(result.metadata.evaluated_matches)} match(s) évalué(s)`}
                />
                <StatTile
                  label="Meilleure value"
                  value={
                    summary.best
                      ? `${formatMetric(summary.best.opportunity_score)} · ${football1x2Labels[summary.best.selection]}`
                      : "Indisponible"
                  }
                  hint={summary.best ? `rang ${summary.best.rank} · score EV + Edge` : undefined}
                  tone="value"
                />
                <StatTile
                  label="EV moyen"
                  value={formatSignedPercent(summary.averageEv)}
                  hint={`sur ${formatCount(summary.displayed)} affiché(s)`}
                />
                <StatTile
                  label="Edge moyen"
                  value={formatPoints(summary.averageEdge)}
                  hint={`sur ${formatCount(summary.displayed)} affiché(s)`}
                />
              </dl>

              {result.items.length === 0 ? (
                <div
                  role="status"
                  className="rounded-2xl border border-dashed border-border-strong px-6 py-16 text-center"
                >
                  <h2 className="text-lg font-medium">Aucune opportunité éligible</h2>
                  <p className="mx-auto mt-2 max-w-lg text-sm text-muted">
                    Le moteur a évalué {formatCount(result.metadata.evaluated_matches)} match(s) et
                    n&apos;a retenu aucune sélection avec ces critères. C&apos;est un résultat, pas
                    une erreur : les motifs de rejet sont détaillés ci-dessous.
                  </p>
                </div>
              ) : (
                <ul
                  aria-label="Opportunités classées"
                  className="grid list-none gap-4 lg:grid-cols-2"
                >
                  {result.items.map((pick) => (
                    <li key={`${pick.match_id}-${pick.selection}`}>
                      <AiPickCard pick={pick} onOpenDetail={() => setDetail(pick)} />
                    </li>
                  ))}
                </ul>
              )}

              {pageInfo.pageCount > 1 ? (
                <nav
                  aria-label="Pagination des opportunités"
                  className="flex flex-wrap items-center justify-between gap-3"
                >
                  <p className="text-xs text-muted">
                    {formatCount(pageInfo.rangeStart)}–{formatCount(pageInfo.rangeEnd)} sur{" "}
                    {formatCount(result.total)}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!pageInfo.hasPrevious}
                      onClick={() => setPage((current) => Math.max(0, current - 1))}
                    >
                      Précédent
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!pageInfo.hasNext}
                      onClick={() => setPage((current) => current + 1)}
                    >
                      Suivant
                    </Button>
                  </div>
                </nav>
              ) : null}

              <ExclusionsPanel exclusions={result.exclusions} />

              <p className="text-xs leading-5 text-faint">
                Classement <span className="font-mono">{result.metadata.ranking_order}</span>. Score{" "}
                <span className="font-mono">{result.metadata.scoring_formula}</span>. Seuils
                appliqués : edge {formatPoints(result.metadata.minimum_edge)}, EV{" "}
                {formatSignedPercent(result.metadata.minimum_ev)}, âge maximal des cotes{" "}
                {formatCount(Math.round(result.metadata.maximum_odds_age_seconds / 3600))} h.
              </p>
            </div>
          );
        }}
      </QueryBoundary>

      <AiPickDetailDialog pick={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

/** League names present in a response, taken from picks and exclusions alike. */
function leaguesIn(result: AiPicksResult | undefined): string[] {
  if (!result) return [];

  const names = new Set<string>();
  for (const item of result.items) names.add(item.league);
  for (const item of result.exclusions) names.add(item.league);

  return [...names].sort((a, b) => a.localeCompare(b, "fr-FR"));
}
