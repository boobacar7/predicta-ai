"use client";

import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary, type EmptyCopy } from "@/components/domain/query-boundary";
import { Input } from "@/components/ui/input";
import { CardSkeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import type { Envelope } from "@/types/api";
import type { ListResult } from "@/types/datasource";
import type { UseQueryResult } from "@tanstack/react-query";
import type { ReactNode } from "react";

export interface CatalogSearch {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  /** Accessible name for the search field. */
  label: string;
}

export interface CatalogBrowserProps<T> {
  title: string;
  eyebrow: string;
  description: string;
  query: UseQueryResult<Envelope<ListResult<T>>>;
  /** Omit for catalogues small enough to browse without searching. */
  search?: CatalogSearch;
  empty: EmptyCopy;
  itemKey: (item: T) => string;
  renderItem: (item: T) => ReactNode;
  /** Grid template classes, so each catalogue can pick its own density. */
  gridClassName?: string;
}

/**
 * Shared shell for the league, team and player catalogues.
 *
 * The three pages differ only in their copy, grid density and card contents, so
 * the header, search field, async states and layout live here once.
 */
export function CatalogBrowser<T>({
  title,
  eyebrow,
  description,
  query,
  search,
  empty,
  itemKey,
  renderItem,
  gridClassName = "grid gap-3 sm:grid-cols-2 xl:grid-cols-3",
}: CatalogBrowserProps<T>) {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={eyebrow} title={title} description={description} />

      {search ? (
        <div className="max-w-sm">
          <Input
            type="search"
            value={search.value}
            onChange={(event) => search.onChange(event.target.value)}
            placeholder={search.placeholder}
            aria-label={search.label}
          />
        </div>
      ) : null}

      <QueryBoundary
        query={query}
        skeleton={
          <div className={cn(gridClassName)}>
            <CardSkeleton rows={2} />
            <CardSkeleton rows={2} />
            <CardSkeleton rows={2} />
          </div>
        }
        isEmpty={(result) => result.items.length === 0}
        empty={empty}
      >
        {(result) => (
          <>
            <p className="sr-only" role="status">
              {result.total} résultats.
            </p>
            <div className={cn(gridClassName)}>
              {result.items.map((item) => (
                <div key={itemKey(item)}>{renderItem(item)}</div>
              ))}
            </div>
          </>
        )}
      </QueryBoundary>
    </div>
  );
}
