"use client";

import type { MockScenario } from "@/types/api";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

/**
 * Mock-only control plane.
 *
 * The selected scenario decides which fixture variant the mock data source
 * serves, so loading, empty, partial, stale and error states can be inspected
 * without a backend. It lives in the mock layer on purpose: when every resource
 * is served over HTTP, this whole module is deleted and no user-facing filter,
 * view or component changes.
 */

export const MOCK_SCENARIOS: ReadonlyArray<{ value: MockScenario; label: string }> = [
  { value: "success", label: "Succès" },
  { value: "empty", label: "Vide" },
  { value: "partial", label: "Partiel" },
  { value: "stale", label: "Stale" },
  { value: "error", label: "Erreur" },
];

interface MockScenarioContextValue {
  scenario: MockScenario;
  setScenario: (scenario: MockScenario) => void;
}

const MockScenarioContext = createContext<MockScenarioContextValue | null>(null);

export function MockScenarioProvider({
  initialScenario = "success",
  children,
}: {
  initialScenario?: MockScenario;
  children: ReactNode;
}) {
  const [scenario, setScenario] = useState<MockScenario>(initialScenario);
  const value = useMemo(() => ({ scenario, setScenario }), [scenario]);

  return <MockScenarioContext.Provider value={value}>{children}</MockScenarioContext.Provider>;
}

/**
 * Returns the active scenario, defaulting to `success` outside a provider so a
 * component can be rendered in isolation (tests, future Storybook) without setup.
 */
export function useMockScenario(): MockScenario {
  return useContext(MockScenarioContext)?.scenario ?? "success";
}

export function useMockScenarioControl(): MockScenarioContextValue {
  const context = useContext(MockScenarioContext);

  if (!context) {
    throw new Error("useMockScenarioControl must be used within a MockScenarioProvider.");
  }

  return context;
}
