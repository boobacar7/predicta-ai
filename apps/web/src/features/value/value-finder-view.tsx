"use client";

import { DataFreshness } from "@/components/domain/data-freshness";
import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { ValueBadge } from "@/components/domain/value-badge";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { DialogContent, DialogRoot, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useFilters } from "@/lib/filters/context";
import { formatDecimalOdds, formatPoints, formatProbability, formatSignedPercent } from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { useValueOpportunities } from "@/lib/query/hooks";
import Link from "next/link";

export function ValueFinderView() {
  const { sport, scenario } = useFilters();
  const query = useValueOpportunities({ sport }, scenario);
  const meta = pageMeta["/value"];

  if (query.isLoading) return <CardSkeleton rows={6} />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={meta.eyebrow}
        title={meta.title}
        description={meta.description}
        actions={
          <DialogRoot>
            <DialogTrigger asChild>
              <Button size="sm">Formules</Button>
            </DialogTrigger>
            <DialogContent title="Value Engine 0.1">
              <ul className="space-y-2 text-sm leading-6 text-muted">
                <li>Probabilité implicite brute = 1 / cote décimale</li>
                <li>Overround = somme(1 / cote_i) − 1</li>
                <li>Probabilité no-vig = implicite / somme des implicites</li>
                <li>Edge = p calibrée − p implicite retenue</li>
                <li>EV = (p calibrée × cote) − 1</li>
              </ul>
              <p className="mt-4 text-xs text-faint">
                Toutes les valeurs affichées sont déjà calculées par le moteur mock. L’UI ne
                recalcule pas la référence métier.
              </p>
            </DialogContent>
          </DialogRoot>
        }
      />
      {query.data.data.items.length === 0 ? (
        <EmptyState
          title="Aucun écart de value"
          description="Soit aucune cote n'est disponible, soit aucun écart n'est publié pour ce filtre."
        />
      ) : (
        <div className="grid gap-4">
          {query.data.data.items.map((item) => (
            <Card key={item.id}>
              <CardBody className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs text-faint">{item.match.league.name}</p>
                    <h2 className="text-lg font-medium">
                      {item.match.home.name} · {item.match.away.name}
                    </h2>
                    <p className="text-sm text-muted">{item.selection_label}</p>
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
                <dl className="grid gap-3 sm:grid-cols-4">
                  <Metric label="P calibrée" value={formatProbability(item.calibrated_probability)} />
                  <Metric label="Cote" value={formatDecimalOdds(item.decimal_odds)} />
                  <Metric label="Implicite" value={formatProbability(item.implied_probability_raw)} />
                  <Metric label="EV" value={formatSignedPercent(item.expected_value)} />
                </dl>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <DataFreshness quality={item.quality} />
                  <p className="text-xs text-faint">
                    Edge no-vig {formatPoints(item.edge_no_vig)} · {item.formula_version}
                  </p>
                </div>
                <Link href={`/matches/${item.match.id}`} className="text-sm text-ai-strong hover:underline">
                  Voir le match
                </Link>
              </CardBody>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-elevated px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.16em] text-faint">{label}</p>
      <p className="mt-1 font-mono text-sm tabular">{value}</p>
    </div>
  );
}
