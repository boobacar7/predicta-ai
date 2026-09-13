"use client";

import type { DataMode, Envelope } from "@/types/api";
import { useQueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";

function isEnvelope(value: unknown): value is Envelope<unknown> {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Envelope<unknown>>;
  return candidate.data_mode === "mock" || candidate.data_mode === "live";
}

/**
 * Envelope `data_mode` currently sitting in the React Query cache.
 *
 * Distinct from `getDataSourceKind()`: an HTTP client can still receive
 * `data_mode: "mock"` when the API is serving fixtures, and that label must
 * appear in chrome rather than only in per-view notices.
 *
 * Mock wins when mixed envelopes are on screen.
 */
export function readObservedDataMode(
  envelopes: ReadonlyArray<unknown>,
): DataMode | null {
  let seenLive = false;

  for (const value of envelopes) {
    if (!isEnvelope(value)) continue;
    if (value.data_mode === "mock") return "mock";
    if (value.data_mode === "live") seenLive = true;
  }

  return seenLive ? "live" : null;
}

export function useObservedEnvelopeDataMode(): DataMode | null {
  const client = useQueryClient();

  return useSyncExternalStore(
    (onStoreChange) => client.getQueryCache().subscribe(onStoreChange),
    () =>
      readObservedDataMode(client.getQueryCache().getAll().map((query) => query.state.data)),
    () => null,
  );
}
