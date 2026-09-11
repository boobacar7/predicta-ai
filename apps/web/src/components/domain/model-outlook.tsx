import { ModelFavoriteBadge } from "@/components/domain/model-favorite-badge";
import { ProbabilityOverview } from "@/components/domain/probability-overview";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import type { FootballAiAnalystReport } from "@/types/api";

export function ModelOutlook({ report }: { report: FootballAiAnalystReport }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Model Outlook</CardTitle>
        <ModelFavoriteBadge selection={report.model_favorite} />
      </CardHeader>
      <CardBody className="space-y-4">
        <p className="text-xs text-muted">
          Probabilités 1X2 publiées par {report.prediction.model_version}. Le favori est celui du
          backend, jamais recalculé ici.
        </p>
        <ProbabilityOverview
          home={report.prediction.home_probability}
          draw={report.prediction.draw_probability}
          away={report.prediction.away_probability}
          favorite={report.model_favorite}
        />
      </CardBody>
    </Card>
  );
}
