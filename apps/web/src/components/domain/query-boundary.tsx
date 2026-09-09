"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { QualityNotice } from "@/components/domain/data-freshness";
import { CardSkeleton } from "@/components/ui/skeleton";
import type { DataQuality, Envelope } from "@/types/api";
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

export interface EmptyCopy {
  title: string;
  description: string;
  action?: ReactNode;
}

export interface QueryBoundaryProps<T> {
  query: UseQueryResult<Envelope<T>>;
  /** Shown while the first response is in flight. */
  skeleton?: ReactNode;
  /** Shown when the query is disabled, for example while an id is unresolved. */
  idle?: ReactNode;
  /** Declares what "no results" means for this payload. */
  isEmpty?: (data: T) => boolean;
  empty?: EmptyCopy;
  /** Surfaces partial or stale payloads above the content. */
  quality?: (data: T) => DataQuality | null | undefined;
  children: (data: T, envelope: Envelope<T>) => ReactNode;
}

/**
 * The single place every data-driven view resolves its async states.
 *
 * Centralising loading, error, empty, partial and stale here is what keeps the
 * mandatory states of docs/product-spec.md §10 consistent across pages, and stops
 * a view from rendering a blank screen or inventing a placeholder number.
 */
export function QueryBoundary<T>({
  query,
  skeleton,
  idle = null,
  isEmpty,
  empty,
  quality,
  children,
}: QueryBoundaryProps<T>) {
  // React Query reports a disabled query as pending with an idle fetch status.
  if (query.isPending && query.fetchStatus === "idle") {
    return <>{idle}</>;
  }

  if (query.isPending) {
    return <>{skeleton ?? <CardSkeleton rows={4} />}</>;
  }

  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const envelope = query.data;
  const payload = envelope.data;

  if (isEmpty?.(payload) && empty) {
    return <EmptyState {...empty} />;
  }

  const payloadQuality = quality?.(payload);

  return (
    <>
      {payloadQuality ? <QualityNotice quality={payloadQuality} /> : null}
      {children(payload, envelope)}
    </>
  );
}
