"use client";

import { ErrorState } from "@/components/domain/empty-state";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import { Unavailable } from "@/components/domain/unavailable";
import { CardSkeleton } from "@/components/ui/skeleton";
import { usePlayer } from "@/lib/query/hooks";

export function PlayerDetailView({ playerId }: { playerId: string }) {
  const query = usePlayer(playerId);

  if (query.isLoading) return <CardSkeleton rows={5} />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  const detail = query.data.data;
  const minutes = detail.stats.find((stat) => stat.key === "minutes");

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={detail.player.country}
        title={detail.player.name}
        description={`${detail.player.position ?? "Rôle indisponible"} · ${detail.team?.name ?? "Indépendant"}`}
      />
      {minutes?.quality.availability === "unavailable" ? (
        <Unavailable label="Minutes" reason={minutes.quality.note ?? "Indicateur absent."} />
      ) : (
        <MetricCard
          label="Minutes mock"
          value={minutes?.value ?? "Indisponible"}
          hint={minutes?.quality.note ?? undefined}
        />
      )}
      {detail.unavailable_fields.map((field) => (
        <Unavailable key={field.field} label={field.field} reason={field.reason} />
      ))}
    </div>
  );
}
