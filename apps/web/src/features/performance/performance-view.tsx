"use client";

import { DataFreshness } from "@/components/domain/data-freshness";
import { MetricCard } from "@/components/domain/metric-card";
import { PageHeader } from "@/components/domain/page-header";
import {
  CalibrationChart,
  PerformanceChart,
  RoiNote,
} from "@/components/domain/performance-chart";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { formatCount, formatMetric, formatProbability } from "@/lib/format/numbers";
import { pageMeta } from "@/lib/navigation";
import { usePerformance } from "@/lib/query/hooks";

const meta = pageMeta["/performance"];

export function PerformanceView() {
  const query = usePerformance();

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <QueryBoundary
        query={query}
        skeleton={<CardSkeleton rows={8} />}
        quality={(report) => report.summary.quality}
      >
        {(report) => (
          <div className="space-y-6">
            <section aria-label="Métriques du modèle" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Log loss"
                value={formatMetric(report.summary.log_loss)}
                hint="Pénalise les probabilités trop confiantes"
                tone="ai"
              />
              <MetricCard
                label="Brier score"
                value={formatMetric(report.summary.brier_score)}
                hint="Erreur quadratique moyenne des probabilités"
              />
              <MetricCard
                label="Accuracy"
                value={formatProbability(report.summary.accuracy)}
                hint="Jamais optimisée seule"
              />
              <MetricCard
                label="Prédictions"
                value={formatCount(report.summary.prediction_count)}
                hint={report.summary.window_label}
              />
            </section>

            <div className="flex flex-wrap items-center gap-3">
              <DataFreshness quality={report.summary.quality} />
              <p className="text-xs text-faint">
                Modèle {report.summary.model_version} · ECE {formatMetric(report.summary.ece)}
              </p>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle>Log loss et Brier dans le temps</CardTitle>
                </CardHeader>
                <CardBody>
                  {report.series.length === 0 ? (
                    <p className="text-sm text-muted">
                      Aucune série historique disponible pour cette fenêtre.
                    </p>
                  ) : (
                    <PerformanceChart series={report.series} />
                  )}
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Calibration</CardTitle>
                </CardHeader>
                <CardBody>
                  {report.calibration.length === 0 ? (
                    <p className="text-sm text-muted">
                      Aucune courbe de calibration disponible pour cette fenêtre.
                    </p>
                  ) : (
                    <CalibrationChart buckets={report.calibration} />
                  )}
                </CardBody>
              </Card>
            </div>

            <RoiNote
              roi={report.summary.theoretical_roi}
              maxDrawdown={report.summary.theoretical_max_drawdown}
            />

            {report.notes.length > 0 ? (
              <section className="space-y-2">
                <h2 className="text-sm font-medium">Notes méthodologiques</h2>
                <ul className="space-y-2 text-sm text-muted">
                  {report.notes.map((note) => (
                    <li key={note}>• {note}</li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}
