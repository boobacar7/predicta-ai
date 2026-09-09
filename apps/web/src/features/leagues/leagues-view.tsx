"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { sportLabels } from "@/lib/format/labels";
import { pageMeta } from "@/lib/navigation";
import { useLeagues } from "@/lib/query/hooks";
import Link from "next/link";

export function LeaguesView() {
  const { sport } = useFilters();
  const query = useLeagues({ sport });
  const meta = pageMeta["/leagues"];

  if (query.isLoading) return <CardSkeleton />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      {query.data.data.items.length === 0 ? (
        <EmptyState title="Aucune ligue" description="Aucune compétition mock pour ce sport." />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {query.data.data.items.map((league) => (
            <Link key={league.id} href={`/leagues/${league.id}`}>
              <Card className="transition-colors hover:border-border-strong">
                <CardBody>
                  <p className="text-xs uppercase tracking-[0.16em] text-faint">
                    {sportLabels[league.sport]}
                  </p>
                  <h2 className="mt-2 text-xl font-medium">{league.name}</h2>
                  <p className="mt-1 text-sm text-muted">
                    {league.country} · {league.season}
                  </p>
                </CardBody>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
