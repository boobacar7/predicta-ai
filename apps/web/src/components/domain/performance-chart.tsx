"use client";

import { formatSignedPercent } from "@/lib/format/numbers";
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
  const summary = series
    .map((point) => `${point.period}: log loss ${point.log_loss ?? "n/a"}`)
    .join(" · ");

  return (
    <div className="h-64">
      <p className="sr-only">Série de log loss : {summary}</p>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series}>
          <CartesianGrid stroke="rgba(245,247,250,0.06)" vertical={false} />
          <XAxis dataKey="period" stroke="#8992A3" fontSize={12} tickLine={false} />
          <YAxis stroke="#8992A3" fontSize={12} tickLine={false} width={40} />
          <Tooltip
            contentStyle={{
              background: "#151b25",
              border: "1px solid rgba(245,247,250,0.1)",
              borderRadius: 12,
            }}
          />
          <Line type="monotone" dataKey="log_loss" stroke="#7c6cf6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="brier_score" stroke="#4ea3d9" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CalibrationChart({ buckets }: { buckets: CalibrationBucket[] }) {
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
          <CartesianGrid stroke="rgba(245,247,250,0.06)" />
          <XAxis
            type="number"
            dataKey="predicted"
            domain={[0, 1]}
            stroke="#8992A3"
            fontSize={12}
            name="Prédit"
          />
          <YAxis
            type="number"
            dataKey="observed"
            domain={[0, 1]}
            stroke="#8992A3"
            fontSize={12}
            name="Observé"
          />
          <Tooltip
            contentStyle={{
              background: "#151b25",
              border: "1px solid rgba(245,247,250,0.1)",
              borderRadius: 12,
            }}
          />
          <Scatter data={buckets} fill="#7c6cf6" />
          <Line
            data={[
              { predicted: 0, observed: 0 },
              { predicted: 1, observed: 1 },
            ]}
            dataKey="observed"
            stroke="#8992A3"
            dot={false}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RoiNote({ value }: { value: number | null }) {
  return (
    <p className="text-sm text-muted">
      ROI théorique {formatSignedPercent(value)}. Mesure de backtest, pas un rendement promis.
    </p>
  );
}
