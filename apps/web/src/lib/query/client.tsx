"use client";

import { toDataSourceError } from "@/lib/api/errors";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

const MAX_RETRIES = 2;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        // Only transport-level failures are worth repeating. A missing entity or a
        // contract violation would fail identically, so it surfaces immediately.
        retry: (failureCount, error) =>
          failureCount < MAX_RETRIES && toDataSourceError(error).retryable,
        // Bounded backoff, so a genuinely failing read reaches its error state in
        // about two seconds instead of leaving the user on a skeleton.
        retryDelay: (attempt) => Math.min(500 * 2 ** attempt, 5_000),
      },
    },
  });
}

export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(createQueryClient);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
