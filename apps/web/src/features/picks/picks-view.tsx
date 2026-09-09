"use client";

import { PageHeader } from "@/components/domain/page-header";
import { PredictionCard } from "@/components/domain/prediction-card";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { pageMeta } from "@/lib/navigation";
import { usePicks } from "@/lib/query/hooks";

const meta = pageMeta["/picks"];

export function PicksView() {
  const { sport } = useFilters();
  const query = usePicks({ sport });

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <p className="max-w-3xl rounded-xl border border-border bg-surface px-4 py-3 text-sm text-muted">
        Un pick est un signal statistique issu d&apos;une prédiction versionnée, accompagné du
        critère qui l&apos;a déclenché. Ce n&apos;est ni un conseil de mise, ni une prévision du
        résultat réel.
      </p>

      <QueryBoundary
        query={query}
        skeleton={
          <div className="grid gap-4 lg:grid-cols-2">
            <CardSkeleton rows={5} />
            <CardSkeleton rows={5} />
          </div>
        }
        isEmpty={(result) => result.items.length === 0}
        empty={{
          title: "Aucun pick publié",
          description:
            "Les picks n'apparaissent que lorsqu'un critère documenté est satisfait. Une absence de pick est un résultat valide, pas une erreur.",
        }}
      >
        {(result) => (
          <div className="grid gap-4 lg:grid-cols-2">
            {result.items.map((pick) => (
              <PredictionCard key={pick.id} pick={pick} />
            ))}
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}
