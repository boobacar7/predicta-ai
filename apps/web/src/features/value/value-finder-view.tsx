"use client";

import { DataFreshness } from "@/components/domain/data-freshness";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { ValueBadge } from "@/components/domain/value-badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { DialogContent, DialogRoot, DialogTrigger } from "@/components/ui/dialog";
import { CardSkeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { sortValueOpportunities, type ValueSort } from "@/features/value/selectors";
import { useFilters } from "@/lib/filters/context";
import { formatAbsolute } from "@/lib/format/dates";
import {
  formatDecimalOdds,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { useValueOpportunities } from "@/lib/query/hooks";
import type { ValueOpportunity } from "@/types/api";
import Link from "next/link";
import { useState } from "react";

const meta = pageMeta["/value"];

const sortOptions: Array<{ value: ValueSort; label: string }> = [
  { value: "edge", label: "Edge no-vig" },
  { value: "expected_value", label: "EV" },
  { value: "kickoff", label: "Coup d'envoi" },
];

export function ValueFinderView() {
  const { sport } = useFilters();
  const [sort, setSort] = useState<ValueSort>("edge");
  const query = useValueOpportunities({ sport });

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={meta.eyebrow}
        title={meta.title}
        description={meta.description}
        actions={<FormulaDialog />}
      />

      <label className="flex w-fit flex-col gap-1 text-xs text-muted">
        Trier par
        <select
          value={sort}
          onChange={(event) => setSort(event.target.value as ValueSort)}
          className="h-9 rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground"
        >
          {sortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

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
        {(result) => (
          <div className="grid gap-4">
            {sortValueOpportunities(result.items, sort).map((item) => (
              <OpportunityCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}

function OpportunityCard({ item }: { item: ValueOpportunity }) {
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
              {item.market} · {item.selection_label}
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
            {item.odds_observed_at ? ` · cote observée le ${formatAbsolute(item.odds_observed_at)}` : ""}
          </p>
        </div>

        <Link
          href={`/matches/${item.match.id}`}
          className="inline-block text-sm text-ai-strong hover:underline"
        >
          Voir le match
        </Link>
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
