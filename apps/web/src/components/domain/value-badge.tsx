import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { formatPoints, formatSignedPercent } from "@/lib/format/numbers";
import type { ValuePreview } from "@/types/api";

export function ValueBadge({
  preview,
  kind = "edge",
}: {
  preview: ValuePreview | null;
  kind?: "edge" | "ev";
}) {
  if (!preview || preview.quality.availability === "unavailable") {
    return <Badge tone="muted">Value indisponible</Badge>;
  }

  const stale = preview.quality.availability === "stale";
  const value = kind === "ev" ? preview.expected_value : preview.edge;
  const label = kind === "ev" ? formatSignedPercent(value) : formatPoints(value);
  const positive = (value ?? 0) > 0;

  return (
    <Tooltip
      content={
        stale
          ? "Cote trop ancienne : l'écart n'est pas actionnable."
          : `Formulé par ${preview.formula_version}. Edge = p calibrée − p implicite.`
      }
    >
      <span>
        <Badge tone={stale ? "warning" : positive ? "value" : "muted"}>
          {kind === "ev" ? "EV" : "Edge"} {label}
          {stale ? " · stale" : ""}
        </Badge>
      </span>
    </Tooltip>
  );
}
