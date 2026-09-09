import { cn } from "@/lib/cn";
import type { HTMLAttributes } from "react";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("animate-pulse rounded-xl bg-surface-elevated", className)}
      {...props}
    />
  );
}

export function CardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-5">
      <Skeleton className="h-4 w-32" />
      <div className="mt-4 space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-10 w-full" />
        ))}
      </div>
    </div>
  );
}
