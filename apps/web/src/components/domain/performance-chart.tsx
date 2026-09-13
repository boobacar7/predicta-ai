"use client";

import { formatSignedPercent } from "@/lib/format/numbers";
import { useChartColors } from "@/lib/theme/use-chart-colors";
import type { CalibrationBucket, PerformanceSeriesPoint } from "@/types/api";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function PerformanceChart({ series }: { series: PerformanceSeriesPoint[] }) {
  const colors = useChartColors();
  const summary = series
    .map((point) => `${point.period}: log loss ${point.log_loss ?? "n/a"}`)
    .join(" · ");

  return (
    <div className="h-64">
      <p className="sr-only">Série de log loss : {summary}</p>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series}>
          <CartesianGrid stroke={colors.grid} vertical={false} />
          <XAxis dataKey="period" stroke={colors.axis} fontSize={12} tickLine={false} />
          <YAxis stroke={colors.axis} fontSize={12} tickLine={false} width={40} />
          <Tooltip
            contentStyle={{
              background: colors.tooltipBackground,
              border: `1px solid ${colors.tooltipBorder}`,
              borderRadius: 12,
              color: colors.tooltipText,
            }}
          />
          <Line type="monotone" dataKey="log_loss" stroke={colors.ai} strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="brier_score" stroke={colors.secondary} strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CalibrationChart({ buckets }: { buckets: CalibrationBucket[] }) {
  const colors = useChartColors();
  const summary = buckets
    .map(
      (bucket) =>
        `prédit ${bucket.predicted}, observé ${bucket.observed ?? "indisponible"} (n=${bucket.count})`,
    )
    .join(" · ");

  return (
    <div className="h-64">
      <p className="sr-only">Calibration : {summary}</p>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart>
          <CartesianGrid stroke={colors.grid} />
          <XAxis
            type="number"
            dataKey="predicted"
            domain={[0, 1]}
            stroke={colors.axis}
            fontSize={12}
            name="Prédit"
          />
          <YAxis
            type="number"
            dataKey="observed"
            domain={[0, 1]}
            stroke={colors.axis}
            fontSize={12}
            name="Observé"
          />
          <Tooltip
            contentStyle={{
              background: colors.tooltipBackground,
              border: `1px solid ${colors.tooltipBorder}`,
              borderRadius: 12,
              color: colors.tooltipText,
            }}
          />
          <Scatter data={buckets} fill={colors.ai} />
          <Line
            data={[
              { predicted: 0, observed: 0 },
              { predicted: 1, observed: 1 },
            ]}
            dataKey="observed"
            stroke={colors.axis}
            dot={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Backtest outcome figures.
 *
 * ROI and drawdown are always shown together: a return quoted without its worst
 * decline overstates how comfortable the strategy was to hold.
 */
export function RoiNote({
  roi,
  maxDrawdown,
}: {
  roi: number | null;
  maxDrawdown: number | null;
}) {
  return (
    <p className="text-sm text-muted">
      ROI théorique {formatSignedPercent(roi)} · drawdown maximal{" "}
      {formatSignedPercent(maxDrawdown)}. Mesures de backtest à mises unitaires, pas un rendement
      promis.
    </p>
  );
}
