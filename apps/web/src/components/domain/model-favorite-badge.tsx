import { Badge } from "@/components/ui/badge";
import { football1x2Labels } from "@/lib/format/labels";

export function ModelFavoriteBadge({
  selection,
}: {
  selection: "HOME" | "DRAW" | "AWAY";
}) {
  return (
    <Badge tone="ai" aria-label={`Favori du modèle : ${football1x2Labels[selection]}`}>
      Favori du modèle · {football1x2Labels[selection]}
    </Badge>
  );
}
