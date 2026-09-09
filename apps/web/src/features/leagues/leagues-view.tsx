"use client";

import { CatalogBrowser } from "@/components/domain/catalog-browser";
import { EntityCard } from "@/components/domain/entity-card";
import { useFilters } from "@/lib/filters/context";
import { sportLabels } from "@/lib/format/labels";
import { pageMeta } from "@/lib/navigation";
import { useLeagues } from "@/lib/query/hooks";

const meta = pageMeta["/leagues"];

export function LeaguesView() {
  const { sport } = useFilters();
  const query = useLeagues({ sport });

  return (
    <CatalogBrowser
      eyebrow={meta.eyebrow}
      title={meta.title}
      description={meta.description}
      query={query}
      gridClassName="grid gap-4 md:grid-cols-2"
      empty={{
        title: "Aucune compétition",
        description: "Aucune compétition n'est référencée pour ce sport.",
      }}
      itemKey={(league) => league.id}
      renderItem={(league) => (
        <EntityCard
          href={`/leagues/${league.id}`}
          title={league.name}
          subtitle={`${sportLabels[league.sport]} · ${league.country} · Saison ${league.season}`}
        />
      )}
    />
  );
}
