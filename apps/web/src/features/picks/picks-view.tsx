"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { PredictionCard } from "@/components/domain/prediction-card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { pageMeta } from "@/lib/navigation";
import { usePicks } from "@/lib/query/hooks";

export function PicksView() {
  const { sport, scenario } = useFilters();
  const query = usePicks({ sport }, scenario);
  const meta = pageMeta["/picks"];

  if (query.isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <CardSkeleton rows={5} />
        <CardSkeleton rows={5} />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      {query.data.data.items.length === 0 ? (
        <EmptyState
          title="Aucun pick publié"
          description="Les picks n’apparaissent que lorsqu’un critère documenté est satisfait. Ce n’est jamais une garantie."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {query.data.data.items.map((pick) => (
            <PredictionCard key={pick.id} pick={pick} />
          ))}
        </div>
      )}
    </div>
  );
}
