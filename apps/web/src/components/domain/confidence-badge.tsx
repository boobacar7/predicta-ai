import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { confidenceLabels } from "@/lib/format/labels";
import type { FootballAnalystConfidence } from "@/types/api";

export function ConfidenceBadge({
  confidence,
}: {
  confidence: FootballAnalystConfidence;
}) {
  const tone = confidence.level === "low" ? "warning" : confidence.level === "high" ? "ai" : "muted";

  return (
    <Card>
      <CardHeader>
        <CardTitle>Confiance</CardTitle>
        <Badge tone={tone} aria-label={`Confiance : ${confidenceLabels[confidence.level]}`}>
          {confidenceLabels[confidence.level]}
        </Badge>
      </CardHeader>
      <CardBody className="space-y-3">
        <p className="text-sm leading-6 text-muted-strong">{confidence.basis}</p>
        <p className="text-xs leading-5 text-faint">{confidence.rule}</p>
      </CardBody>
    </Card>
  );
}
