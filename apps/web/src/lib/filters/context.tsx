"use client";

import type { SportCode } from "@/types/api";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/**
 * Cross-page user filters.
 *
 * Only genuinely global filters belong here. Page-scoped filters (date, league,
 * search text) stay in the feature that owns them.
 */

export type SportFilterValue = SportCode | "all";

interface FiltersContextValue {
  sport: SportFilterValue;
  setSport: (sport: SportFilterValue) => void;
}

const FiltersContext = createContext<FiltersContextValue | null>(null);

export function FiltersProvider({
  initialSport = "football",
  children,
}: {
  initialSport?: SportFilterValue;
  children: ReactNode;
}) {
  const [sport, setSport] = useState<SportFilterValue>(initialSport);
  const value = useMemo(() => ({ sport, setSport }), [sport]);

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters(): FiltersContextValue {
  const context = useContext(FiltersContext);

  if (!context) {
    throw new Error("useFilters must be used within a FiltersProvider.");
  }

  return context;
}
