"use client";

import type { MockScenario, SportCode } from "@/types/api";
import { createContext, useContext, type ReactNode } from "react";

export type SportFilterValue = SportCode | "all";

type FiltersContextValue = {
  sport: SportFilterValue;
  setSport: (sport: SportFilterValue) => void;
  scenario: MockScenario;
  setScenario: (scenario: MockScenario) => void;
};

const FiltersContext = createContext<FiltersContextValue | null>(null);

export function FiltersProvider({
  value,
  children,
}: {
  value: FiltersContextValue;
  children: ReactNode;
}) {
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useFilters() {
  const context = useContext(FiltersContext);
  if (!context) {
    throw new Error("useFilters must be used within FiltersProvider");
  }
  return context;
}
