"use client";

import { CatalogBrowser } from "@/components/domain/catalog-browser";
import { EntityCard } from "@/components/domain/entity-card";
import { TeamLogo } from "@/components/domain/team-logo";
import { useFilters } from "@/lib/filters/context";
import { sportLabels } from "@/lib/format/labels";
import { pageMeta } from "@/lib/navigation";
import { usePlayers } from "@/lib/query/hooks";
import { useDeferredValue, useState } from "react";

const meta = pageMeta["/players"];

export function PlayersView() {
  const { sport } = useFilters();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const query = usePlayers({ sport, query: deferredSearch });

  return (
    <CatalogBrowser
      eyebrow={meta.eyebrow}
      title={meta.title}
      description={meta.description}
      query={query}
      gridClassName="grid gap-3 sm:grid-cols-2"
      search={{
        value: search,
        onChange: setSearch,
        placeholder: "Rechercher un joueur",
        label: "Rechercher un joueur",
      }}
      empty={{
        title: "Aucun joueur",
        description: "Aucun profil ne correspond à ce sport ou à cette recherche.",
      }}
      itemKey={(player) => player.id}
      renderItem={(player) => (
        <EntityCard
          href={`/players/${player.id}`}
          title={player.name}
          subtitle={`${sportLabels[player.sport]} · ${player.position ?? "Poste indisponible"}`}
          leading={
            <TeamLogo name={player.name} abbreviation={player.name.slice(0, 2).toUpperCase()} />
          }
        />
      )}
    />
  );
}
