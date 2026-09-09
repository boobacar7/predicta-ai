import { Badge } from "@/components/ui/badge";
import { availabilityLabels } from "@/lib/format/labels";
import { formatAbsolute } from "@/lib/format/dates";
import type { DataQuality } from "@/types/api";

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
