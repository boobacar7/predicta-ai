import { Badge } from "@/components/ui/badge";
import { formatAbsolute } from "@/lib/format/dates";
import { availabilityLabels } from "@/lib/format/labels";
import type { AvailabilityStatus, DataQuality } from "@/types/api";

export function DataFreshness({ quality }: { quality: DataQuality }) {
  const tone =
    quality.availability === "stale" || quality.availability === "partial"
      ? "warning"
      : quality.availability === "unavailable"
        ? "risk"
        : "muted";

  return (
    <Badge tone={tone}>
      {availabilityLabels[quality.availability]}
      {quality.observed_at ? ` · ${formatAbsolute(quality.observed_at)}` : ""}
    </Badge>
  );
}

export function Provenance({ quality }: { quality: DataQuality }) {
  return (
    <p className="text-xs text-faint">
      Source : {quality.source ?? "non fournie"}
      {quality.note ? ` · ${quality.note}` : ""}
    </p>
  );
}

const DEGRADED_COPY: Partial<Record<AvailabilityStatus, string>> = {
  partial: "Certaines valeurs de cette vue sont indisponibles et sont signalées individuellement.",
  stale: "Ce contenu est conservé mais sa fraîcheur n'est plus garantie.",
};

/**
 * Banner shown above a payload that is usable but degraded.
 *
 * Rendering the content with a visible caveat is preferred to hiding it: a stale
 * or partial answer is still information, as long as its limits are stated.
 * Returns nothing when the payload is fully available.
 */
export function QualityNotice({ quality }: { quality: DataQuality }) {
  const copy = DEGRADED_COPY[quality.availability];

  if (!copy) {
    return null;
  }

  return (
    <div
      role="status"
      className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-warning/25 bg-warning-soft px-4 py-3"
    >
      <Badge tone="warning">{availabilityLabels[quality.availability]}</Badge>
      <p className="text-xs text-muted-strong">{copy}</p>
      {quality.observed_at ? (
        <p className="text-xs text-faint">Observé le {formatAbsolute(quality.observed_at)}</p>
      ) : null}
    </div>
  );
}
