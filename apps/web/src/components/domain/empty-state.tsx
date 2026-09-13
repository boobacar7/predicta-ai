import { Button } from "@/components/ui/button";
import { toDataSourceError } from "@/lib/api/errors";
import type { ReactNode } from "react";

/**
 * A genuine absence of results. Distinct from an error, and never rendered as
 * a zero value.
 */
export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div
      role="status"
      className="rounded-2xl border border-dashed border-border-strong px-6 py-16 text-center"
    >
      <h2 className="text-lg font-medium">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">{description}</p>
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/**
 * A failed read.
 *
 * Pass the caught `error` and the copy is derived from the typed data-layer
 * error, including whether retrying could plausibly help. A 404 or a contract
 * violation offers no retry button, because the same request would fail again.
 */
export function ErrorState({
  title = "Impossible de charger ces données",
  description,
  error,
  onRetry,
}: {
  title?: string;
  description?: string;
  error?: unknown;
  onRetry?: () => void;
}) {
  const normalized = error === undefined ? undefined : toDataSourceError(error);
  const message = description ?? normalized?.message ?? "Cause inconnue.";
  const canRetry = Boolean(onRetry) && (normalized?.retryable ?? true);

  return (
    <div
      role="alert"
      className="rounded-2xl border border-risk/30 bg-risk-soft px-6 py-12 text-center"
    >
      <h2 className="text-lg font-medium text-foreground">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted">{message}</p>
      {normalized?.problem?.title ? (
        <p className="mt-2 text-sm text-muted-strong">
          {normalized.status ? `${normalized.status} · ` : ""}
          {normalized.problem.title}
        </p>
      ) : null}
      {normalized?.problem?.type ? (
        <p className="mt-1 font-mono text-xs text-faint">{normalized.problem.type}</p>
      ) : null}
      {normalized?.requestId ? (
        <p className="mt-2 font-mono text-xs text-faint">request_id {normalized.requestId}</p>
      ) : null}
      {canRetry ? (
        <Button className="mt-5" onClick={onRetry}>
          Réessayer
        </Button>
      ) : null}
    </div>
  );
}
