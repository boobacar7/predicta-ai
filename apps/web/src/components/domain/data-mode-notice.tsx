import { Badge } from "@/components/ui/badge";
import type { DataMode } from "@/types/api";

/**
 * States that a specific payload was built from mock data.
 *
 * Distinct from `MockBanner`, which describes how the app is wired: this one
 * reads the `data_mode` the server returned. Both are needed, because the API
 * can be live while the odds behind an answer still come from a mock provider,
 * and in that case the response is honestly labelled `mock`.
 *
 * Renders nothing for a live payload.
 */
export function DataModeNotice({
  dataMode,
  source,
}: {
  dataMode: DataMode;
  /** Provider named by the payload, shown so the claim is verifiable. */
  source?: string | null;
}) {
  if (dataMode !== "mock") {
    return null;
  }

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-warning/25 bg-warning-soft px-4 py-3"
    >
      <Badge tone="warning">Mock data</Badge>
      <p className="text-xs text-muted-strong">
        Données de démonstration. Les cotes affichées proviennent d&apos;un fournisseur fictif
        {source ? (
          <>
            {" "}
            (<span className="font-mono">{source}</span>)
          </>
        ) : null}{" "}
        et ne représentent aucun prix de marché réel.
      </p>
    </div>
  );
}
