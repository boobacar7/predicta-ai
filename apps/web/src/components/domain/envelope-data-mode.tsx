"use client";

import { Badge } from "@/components/ui/badge";
import { useObservedEnvelopeDataMode } from "@/lib/data-mode/observed";

/**
 * Chrome label for the envelope `data_mode` currently in the query cache.
 *
 * `MockBanner` still describes how the app is wired (config kind). This badge
 * reports what the payloads themselves declare, so an HTTP cutover against a
 * fixture API cannot hide `mock`.
 */
export function EnvelopeDataModeBadge() {
  const dataMode = useObservedEnvelopeDataMode();

  if (!dataMode) {
    return null;
  }

  return (
    <Badge
      tone={dataMode === "mock" ? "warning" : "muted"}
      aria-label={`data_mode ${dataMode}`}
    >
      data_mode · {dataMode}
    </Badge>
  );
}
