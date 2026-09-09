"use client";

import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { StatGrid } from "@/components/domain/stat-grid";
import { Unavailable } from "@/components/domain/unavailable";
import { CardSkeleton } from "@/components/ui/skeleton";
import { sportLabels } from "@/lib/format/labels";
import { usePlayer } from "@/lib/query/hooks";
import Link from "next/link";

export function PlayerDetailView({ playerId }: { playerId: string }) {
  const query = usePlayer(playerId);

  return (
    <QueryBoundary query={query} skeleton={<CardSkeleton rows={5} />}>
      {(detail) => (
        <div className="space-y-6">
          <PageHeader
            eyebrow={`${sportLabels[detail.player.sport]} · ${detail.player.country}`}
            title={detail.player.name}
            description={detail.player.position ?? "Poste indisponible"}
          />

          {detail.team ? (
            <p className="text-sm text-muted">
              Équipe :{" "}
              <Link href={`/teams/${detail.team.id}`} className="text-ai-strong hover:underline">
                {detail.team.name}
              </Link>
            </p>
          ) : (
            <Unavailable
              label="Équipe"
              reason="Aucun club n'est associé à ce profil dans le catalogue."
            />
          )}

          <StatGrid stats={detail.stats} />

          {detail.unavailable_fields.length > 0 ? (
            <div className="grid gap-2 md:grid-cols-2">
              {detail.unavailable_fields.map((field) => (
                <Unavailable key={field.field} label={field.field} reason={field.reason} />
              ))}
            </div>
          ) : null}
        </div>
      )}
    </QueryBoundary>
  );
}
