"use client";

import { Badge } from "@/components/ui/badge";
import { MOCK_NOW_ISO } from "@/data/mock/clock";
import { getDataSourceKind } from "@/lib/config";

const COPY = {
  mock: "Données de démonstration fictives. Aucune compétition, cote ou performance réelle n'est représentée.",
  hybrid:
    "Migration en cours : certaines sections lisent l'API et d'autres des fixtures fictives. Chaque réponse expose son data_mode.",
} as const;

/**
 * Permanent notice while any resource is served from fixtures.
 *
 * It is driven by the resolved data source rather than a constant, so it
 * disappears on its own once every resource reads from the API, and correctly
 * reports a partially migrated build instead of claiming everything is mock.
 */
export function MockBanner() {
  const kind = getDataSourceKind();

  if (kind === "http") {
    return null;
  }

  return (
    <div className="border-b border-warning/20 bg-warning-soft px-4 py-2 text-center text-xs text-warning md:text-left">
      <Badge tone="warning" className="mr-2">
        {kind}
      </Badge>
      {COPY[kind]}
      {kind === "mock" ? ` Horloge mock : ${MOCK_NOW_ISO}.` : ""}
    </div>
  );
}
