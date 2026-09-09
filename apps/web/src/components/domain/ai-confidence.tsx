import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import { confidenceLabels } from "@/lib/format/labels";
import type { ConfidenceLevel } from "@/types/api";

export function AIConfidence({ level }: { level: ConfidenceLevel }) {
  const tone = level === "high" ? "ai" : level === "medium" ? "warning" : "muted";

  return (
    <Tooltip content="La confiance reflète la qualité et la stabilité des données et du modèle. Ce n'est pas une certitude sportive.">
      <span>
        <Badge tone={tone}>Confiance {confidenceLabels[level].toLowerCase()}</Badge>
      </span>
    </Tooltip>
  );
}
