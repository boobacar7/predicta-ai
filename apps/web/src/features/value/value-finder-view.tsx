"use client";

import { DataFreshness } from "@/components/domain/data-freshness";
import { DataModeNotice } from "@/components/domain/data-mode-notice";
import {
  DateFilter,
  NumberFilter,
  SelectFilter,
  ThresholdFilter,
} from "@/components/domain/filters";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { ValueBadge } from "@/components/domain/value-badge";
import { ValueDetailDialog } from "@/components/domain/value-detail";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { DialogContent, DialogRoot, DialogTrigger } from "@/components/ui/dialog";
import { CardSkeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import {
  availableMarkets,
  defaultValueFilters,
  filterValueOpportunities,
  paginateValueOpportunities,
  sortValueOpportunities,
  type ValueFilters,
  type ValueSort,
} from "@/features/value/selectors";
import { useFilters } from "@/lib/filters/context";
import { formatAbsolute } from "@/lib/format/dates";
import { formatKickoffOrUnknown } from "@/lib/format/identity";
import {
  formatCount,
  formatDecimalOdds,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { useLeagues, useValueOpportunities } from "@/lib/query/hooks";
import type { ValueOpportunity } from "@/types/api";
import Link from "next/link";
import { useState } from "react";

const meta = pageMeta["/value-finder"];
const PAGE_SIZE = 8;

const sortOptions: Array<{ value: ValueSort; label: string }> = [
  { value: "edge", label: "Edge no-vig" },
  { value: "expected_value", label: "EV" },
  { value: "probability", label: "Probabilité modèle" },
  { value: "odds", label: "Cote" },
  { value: "kickoff", label: "Coup d'envoi" },
];

/**
 * Value Finder, backed by `GET /value`.
 *
 * The endpoint accepts `sport`, `league_id`, `date`, `status`, `limit` and
 * `offset` and nothing else. Those are sent to the API, so the server decides
 * which opportunities exist.
 *
 * Market, the four numeric thresholds and the sort order have no equivalent
 * query parameter in the contract. They are applied here as a refinement over
 * the loaded set, and paging follows the refinement so the page count always
 * matches what is on screen. Refining server-side would require new parameters
 * on `GET /value`; that is a backend change and is documented as a gap in
 * docs/frontend-handoff.md rather than worked around by inventing an endpoint.
 *
 * The two groups are labelled in the UI so a reader can tell which criteria the
 * API enforced from which the browser applied.
 *
 * No ratio is recomputed: every figure comes from the Value Engine.
 */
export function ValueFinderView() {
  const { sport } = useFilters();
  const [sort, setSort] = useState<ValueSort>("edge");
  const [filters, setFilters] = useState<ValueFilters>(defaultValueFilters);
  const [date, setDate] = useState("");
  const [league, setLeague] = useState<string>("all");
  const [page, setPage] = useState(1);
  const [detail, setDetail] = useState<ValueOpportunity | null>(null);

  const query = useValueOpportunities({
    sport,
    league_id: league === "all" ? undefined : league,
    date: date || undefined,
  });
  const leaguesQuery = useLeagues({ sport });

  const update = <K extends keyof ValueFilters>(key: K) => (value: ValueFilters[K]) => {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  };

  const hasRefinement =
    date !== "" ||
    league !== "all" ||
    filters.market !== "all" ||
    filters.minEdge !== null ||
    filters.minEv !== null ||
    filters.minProbability !== null ||
    filters.minOdds !== null;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={meta.eyebrow}
        title={meta.title}
        description={meta.description}
        actions={<FormulaDialog />}
      />

      <QueryBoundary
        query={query}
        skeleton={<CardSkeleton rows={6} />}
        isEmpty={(result) => result.items.length === 0}
        empty={{
          title: "Aucun écart de value",
          description:
            "Aucune cote exploitable n'est associée à une probabilité calibrée pour ce filtre. C'est un résultat, pas une erreur.",
        }}
      >
        {(result, envelope) => {
          const markets = availableMarkets(result.items);
          const refined = sortValueOpportunities(
            filterValueOpportunities(result.items, filters),
            sort,
          );
          const paged = paginateValueOpportunities(refined, page, PAGE_SIZE);

          return (
            <div className="space-y-5">
              <DataModeNotice dataMode={envelope.data_mode} />

              <section
                aria-label="Filtres envoyés à l'API"
                className="space-y-2 rounded-2xl border border-border bg-surface px-4 py-3"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-faint">
                  Filtres appliqués par l&apos;API
                </p>
                <div className="flex flex-wrap items-end gap-3">
                  <SelectFilter
                    label="Compétition"
                    value={league}
                    onChange={(value) => {
                      setLeague(value);
                      setPage(1);
                    }}
                  >
                    <option value="all">Toutes</option>
                    {(leaguesQuery.data?.data.items ?? []).map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </SelectFilter>

                  <DateFilter
                    value={date}
                    onChange={(value) => {
                      setDate(value);
                      setPage(1);
                    }}
                  />
                </div>
              </section>

              <section
                aria-label="Affinage local des opportunités"
                className="space-y-2 rounded-2xl border border-border bg-surface px-4 py-3"
              >
                <p className="text-xs uppercase tracking-[0.14em] text-faint">
                  Affinage local · non supporté par <span className="font-mono">GET /value</span>
                </p>
                <div className="flex flex-wrap items-end gap-3">
                <SelectFilter
                  label="Marché"
                  value={filters.market}
                  onChange={update("market")}
                >
                  <option value="all">Tous</option>
                  {markets.map((market) => (
                    <option key={market} value={market}>
                      {market}
                    </option>
                  ))}
                </SelectFilter>

                <ThresholdFilter
                  label="Edge min"
                  value={filters.minEdge}
                  onChange={update("minEdge")}
                />
                <ThresholdFilter
                  label="EV min"
                  value={filters.minEv}
                  onChange={update("minEv")}
                  suffix="%"
                  step={1}
                />
                <ThresholdFilter
                  label="Proba min"
                  value={filters.minProbability}
                  onChange={update("minProbability")}
                  suffix="%"
                  step={5}
                />
                <NumberFilter
                  label="Cote min"
                  value={filters.minOdds}
                  onChange={update("minOdds")}
                  min={1}
                />

                <SelectFilter
                  label="Trier par"
                  value={sort}
                  onChange={(value) => setSort(value as ValueSort)}
                >
                  {sortOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </SelectFilter>

                {hasRefinement ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setFilters(defaultValueFilters);
                      setDate("");
                      setLeague("all");
                      setPage(1);
                    }}
                  >
                    Réinitialiser
                  </Button>
                ) : null}
                </div>
              </section>

              <p className="text-xs text-muted">
                {formatCount(paged.total)} opportunité(s) retenue(s) sur{" "}
                {formatCount(result.items.length)} chargée(s).
              </p>

              {paged.items.length === 0 ? (
                <div
                  role="status"
                  className="rounded-2xl border border-dashed border-border-strong px-6 py-16 text-center"
                >
                  <h2 className="text-lg font-medium">Aucune opportunité pour ces critères</h2>
                  <p className="mx-auto mt-2 max-w-lg text-sm text-muted">
                    Les seuils écartent toutes les opportunités chargées. Une valeur non mesurée ne
                    franchit jamais un seuil : elle est exclue plutôt que comptée comme nulle.
                  </p>
                </div>
              ) : (
                <ul className="grid list-none gap-4">
                  {paged.items.map((item) => (
                    <li key={item.id}>
                      <OpportunityCard item={item} onOpenDetail={() => setDetail(item)} />
                    </li>
                  ))}
                </ul>
              )}

              {paged.pageCount > 1 ? (
                <nav
                  aria-label="Pagination des opportunités"
                  className="flex flex-wrap items-center justify-between gap-3"
                >
                  <p className="text-xs text-muted">
                    Page {formatCount(paged.page)} sur {formatCount(paged.pageCount)}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!paged.hasPrevious}
                      onClick={() => setPage((current) => current - 1)}
                    >
                      Précédent
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={!paged.hasNext}
                      onClick={() => setPage((current) => current + 1)}
                    >
                      Suivant
                    </Button>
                  </div>
                </nav>
              ) : null}
            </div>
          );
        }}
      </QueryBoundary>

      <ValueDetailDialog opportunity={detail} onClose={() => setDetail(null)} />
    </div>
  );
}

function OpportunityCard({
  item,
  onOpenDetail,
}: {
  item: ValueOpportunity;
  onOpenDetail: () => void;
}) {
  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-faint">{item.match.league.name}</p>
            <h2 className="text-lg font-medium">
              {item.match.home.name} · {item.match.away.name}
            </h2>
            <p className="text-sm text-muted">
              {formatKickoffOrUnknown(item.match.kickoff_at)} · {item.market} ·{" "}
              {item.selection_label}
            </p>
          </div>
          <ValueBadge
            preview={{
              selection: item.selection,
              edge: item.edge_no_vig,
              expected_value: item.expected_value,
              formula_version: item.formula_version,
              quality: item.quality,
            }}
          />
        </div>

        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile
            label="P calibrée"
            value={formatProbability(item.calibrated_probability)}
            tone="ai"
          />
          <StatTile label="Cote" value={formatDecimalOdds(item.decimal_odds)} />
          <StatTile label="Implicite" value={formatProbability(item.implied_probability_raw)} />
          <StatTile label="No-vig" value={formatProbability(item.no_vig_probability)} />
          <StatTile label="Edge no-vig" value={formatPoints(item.edge_no_vig)} tone="value" />
          <StatTile label="EV" value={formatSignedPercent(item.expected_value)} tone="value" />
        </dl>

        <div className="flex flex-wrap items-center justify-between gap-2">
          <DataFreshness quality={item.quality} />
          <p className="text-xs text-faint">
            Overround {formatPoints(item.overround)} · formule {item.formula_version}
            {item.odds_observed_at
              ? ` · cote observée le ${formatAbsolute(item.odds_observed_at)}`
              : ""}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            onClick={onOpenDetail}
            className="text-sm text-ai-strong hover:underline"
          >
            Détail de l&apos;opportunité
          </button>
          <Link
            href={`/matches/${item.match.id}`}
            className="text-sm text-muted hover:text-foreground hover:underline"
          >
            Voir le match
          </Link>
        </div>
      </CardBody>
    </Card>
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
          <li>Overround = somme(1 / cote_i) − 1</li>
          <li>Probabilité no-vig = implicite_i / somme des implicites</li>
          <li>Edge = probabilité calibrée − probabilité implicite retenue</li>
          <li>EV = (probabilité calibrée × cote décimale) − 1</li>
        </ul>
        <p className="mt-4 text-xs text-faint">
          Ces valeurs sont calculées et versionnées par le Value Engine côté serveur.
          L&apos;interface les affiche telles quelles et ne recalcule aucune référence métier.
        </p>
      </DialogContent>
    </DialogRoot>
  );
}
