import { CandidateModelNotice } from "@/components/domain/model-status";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import { formatAbsolute } from "@/lib/format/dates";
import { formatKickoffOrUnknown } from "@/lib/format/identity";
import { availabilityLabels, freshnessLabels, modelStatusLabels } from "@/lib/format/labels";
import type { FootballAiAnalystReport } from "@/types/api";

export function DataQualityPanel({ report }: { report: FootballAiAnalystReport }) {
  const quality = report.analyst.data_quality;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Data Quality</CardTitle>
        <Badge tone={quality.model_status === "candidate" ? "warning" : "ai"}>
          {modelStatusLabels[quality.model_status]}
        </Badge>
      </CardHeader>
      <CardBody className="space-y-4">
        <CandidateModelNotice
          version={report.prediction.model_version}
          status={report.prediction.model_status}
        />
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatTile label="data_mode" value={quality.data_mode} />
          <StatTile label="model_status" value={quality.model_status} />
          <StatTile label="model_version" value={report.prediction.model_version} />
          <StatTile label="dataset_version" value={report.prediction.dataset_version} />
          <StatTile label="analysis_version" value={report.analyst.analysis_version} />
          <StatTile label="provider" value={report.analyst.provider} />
          <StatTile label="cutoff_at" value={formatKickoffOrUnknown(quality.cutoff_at)} />
          <StatTile label="generated_at" value={formatAbsolute(report.analyst.generated_at)} />
          <StatTile
            label="freshness"
            value={quality.freshness ? freshnessLabels[quality.freshness] : "Information indisponible"}
          />
          <StatTile label="availability" value={availabilityLabels[quality.availability]} />
        </dl>
        {quality.missing.length > 0 ? (
          <p className="text-xs text-muted">
            Champs manquants : {quality.missing.join(", ")}.
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}
