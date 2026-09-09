"use client";

import { CatalogBrowser } from "@/components/domain/catalog-browser";
import { EntityCard } from "@/components/domain/entity-card";
import { TeamLogo } from "@/components/domain/team-logo";
import { useFilters } from "@/lib/filters/context";
import { sportLabels } from "@/lib/format/labels";
import { pageMeta } from "@/lib/navigation";
import { useTeams } from "@/lib/query/hooks";
import { useDeferredValue, useState } from "react";

const meta = pageMeta["/teams"];

export function TeamsView() {
  const { sport } = useFilters();
  const [search, setSearch] = useState("");
  // Keeps typing responsive: the request follows the settled value, not each keystroke.
  const deferredSearch = useDeferredValue(search);
  const query = useTeams({ sport, query: deferredSearch });

  return (
    <CatalogBrowser
      eyebrow={meta.eyebrow}
      title={meta.title}
      description={meta.description}
      query={query}
      search={{
        value: search,
        onChange: setSearch,
        placeholder: "Rechercher une équipe",
        label: "Rechercher une équipe",
      }}
      empty={{
        title: "Aucune équipe",
        description: "Aucune équipe ne correspond à ce sport ou à cette recherche.",
      }}
      itemKey={(team) => team.id}
      renderItem={(team) => (
        <EntityCard
          href={`/teams/${team.id}`}
          title={team.name}
          subtitle={sportLabels[team.sport]}
          leading={<TeamLogo name={team.name} abbreviation={team.abbreviation} />}
        />
      )}
    />
  );
}
