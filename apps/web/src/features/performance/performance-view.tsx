"use client";

import { EmptyState, ErrorState } from "@/components/domain/empty-state";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import {
  CalibrationChart,
  PerformanceChart,
  RoiNote,
} from "@/components/domain/performance-chart";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/lib/filters/context";
import { formatCount, formatProbability } from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { usePerformance } from "@/lib/query/hooks";

export function PerformanceView() {
  const { scenario } = useFilters();
  const query = usePerformance(scenario);
  const meta = pageMeta["/performance"];

  if (query.isLoading) return <CardSkeleton rows={8} />;
  if (query.isError || !query.data) {
    return <ErrorState description={query.error?.message ?? "Réponse mock indisponible."} onRetry={() => void query.refetch()} />;
  }

  const report = query.data.data;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <section className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Log loss" value={report.summary.log_loss ?? "Indisponible"} tone="ai" />
        <MetricCard label="Brier" value={report.summary.brier_score ?? "Indisponible"} />
        <MetricCard
          label="Accuracy"
          value={formatProbability(report.summary.accuracy)}
          hint="Ne pas optimiser uniquement cette métrique"
        />
        <MetricCard
          label="Prédictions"
          value={formatCount(report.summary.prediction_count)}
          hint={report.summary.window_label}
        />
      </section>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Log loss et Brier</CardTitle>
          </CardHeader>
          <CardBody>
            <PerformanceChart series={report.series} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Calibration</CardTitle>
          </CardHeader>
          <CardBody>
            <CalibrationChart buckets={report.calibration} />
          </CardBody>
        </Card>
      </div>
      <RoiNote value={report.summary.theoretical_roi} />
      {report.notes.length === 0 ? (
        <EmptyState title="Pas de notes" description="Aucune note méthodologique." />
      ) : (
        <ul className="space-y-2 text-sm text-muted">
          {report.notes.map((note) => (
            <li key={note}>• {note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
