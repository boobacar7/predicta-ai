import { Badge } from "@/components/ui/badge";
import { modelStatusLabels } from "@/lib/format/labels";
import type { FootballModelStatus } from "@/types/api";

/**
 * Model identity and lifecycle status.
 *
 * A candidate model has not been promoted, so its status travels with every
 * figure it produced rather than sitting once at the top of the page. Product
 * spec §8 forbids showing a probability without its model version.
 */
export function ModelStatusBadge({
  version,
  status,
}: {
  version: string;
  status: FootballModelStatus;
}) {
  return (
    <Badge tone={status === "candidate" ? "warning" : "ai"}>
      <span className="font-mono">{version}</span>
      <span aria-hidden="true">·</span>
      {modelStatusLabels[status]}
    </Badge>
  );
}

/**
 * Explains what a candidate model means, once per page.
 *
 * Rendered only for a non-promoted model, so the warning keeps its weight
 * instead of becoming permanent furniture.
 *
 * Carried on a neutral surface rather than a warning-coloured one. The page
 * already devotes a warning banner to the mock `data_mode`, and two full-width
 * orange blocks would read as an alarm instead of as context.
 */
export function CandidateModelNotice({
  version,
  status,
}: {
  version: string;
  status: FootballModelStatus;
}) {
  if (status !== "candidate") {
    return null;
  }

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border bg-surface px-4 py-3"
    >
      <Badge tone="warning">Modèle candidat</Badge>
      <p className="text-xs text-muted">
        <span className="font-mono">{version}</span> n&apos;est ni champion ni promu en production.
        Ses probabilités sont des estimations statistiques évaluées, pas une référence validée.
      </p>
    </div>
  );
}
