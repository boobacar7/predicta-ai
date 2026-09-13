"use client";

import { cn } from "@/lib/cn";
import type { SportFilterValue } from "@/lib/filters/context";
import { matchStatusLabels, sportLabels } from "@/lib/format/labels";
import type { MatchStatus, SportCode } from "@/types/api";
import type { ReactNode } from "react";

const sportOptions: Array<{ value: SportFilterValue; label: string }> = [
  { value: "all", label: "Tous les sports" },
  { value: "football", label: sportLabels.football },
  { value: "basketball", label: sportLabels.basketball },
  { value: "tennis", label: sportLabels.tennis },
];

export function SportFilter({
  value,
  onChange,
}: {
  value: SportFilterValue;
  onChange: (value: SportFilterValue) => void;
}) {
  return (
    <div role="group" aria-label="Filtrer par sport" className="flex flex-wrap gap-1">
      {sportOptions.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            "h-8 rounded-full px-3 text-xs font-medium transition-colors",
            value === option.value
              ? "bg-ai-soft text-foreground"
              : "text-muted hover:bg-surface-hover hover:text-foreground",
          )}
          aria-pressed={value === option.value}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Shared select shell, so every dropdown filter looks and behaves the same. */
export function SelectFilter({
  label,
  value,
  onChange,
  disabled,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground disabled:opacity-50"
      >
        {children}
      </select>
    </label>
  );
}

export function LeagueFilter({
  leagues,
  value,
  onChange,
  disabled,
}: {
  leagues: ReadonlyArray<{ id: string; name: string; sport: SportCode }>;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  return (
    <SelectFilter label="Compétition" value={value} onChange={onChange} disabled={disabled}>
      <option value="all">Toutes</option>
      {leagues.map((league) => (
        <option key={league.id} value={league.id}>
          {league.name}
        </option>
      ))}
    </SelectFilter>
  );
}

export function DateFilter({
  value,
  onChange,
  label = "Date",
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground"
      />
    </label>
  );
}

/**
 * Numeric threshold filter.
 *
 * The user types a human unit (percentage points) while the API and the Value
 * Engine work in raw ratios, so the control converts on the way in and out.
 * That is a unit change on a request parameter, never a recomputation of a
 * published metric.
 *
 * An empty field means "no threshold", which is not the same request as `0`.
 */
export function ThresholdFilter({
  label,
  value,
  onChange,
  step = 0.5,
  suffix = "pts",
  placeholder = "—",
}: {
  label: string;
  /** Raw ratio, or null when the threshold is disabled. */
  value: number | null;
  onChange: (value: number | null) => void;
  step?: number;
  suffix?: string;
  placeholder?: string;
}) {
  const displayed = value === null ? "" : String(Number((value * 100).toFixed(4)));

  return (
    <label className="flex flex-col gap-1 text-xs text-muted">
      <span>
        {label} <span className="text-faint">({suffix})</span>
      </span>
      <input
        type="number"
        inputMode="decimal"
        step={step}
        value={displayed}
        placeholder={placeholder}
        onChange={(event) => {
          const raw = event.target.value.trim();
          if (raw === "") return onChange(null);

          const parsed = Number(raw);
          onChange(Number.isFinite(parsed) ? parsed / 100 : null);
        }}
        className="h-9 w-28 rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground"
      />
    </label>
  );
}

/** Plain numeric filter for values already expressed in their own unit, such as odds. */
export function NumberFilter({
  label,
  value,
  onChange,
  step = 0.05,
  min,
  placeholder = "—",
}: {
  label: string;
  value: number | null;
  onChange: (value: number | null) => void;
  step?: number;
  min?: number;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs text-muted">
      {label}
      <input
        type="number"
        inputMode="decimal"
        step={step}
        min={min}
        value={value === null ? "" : String(value)}
        placeholder={placeholder}
        onChange={(event) => {
          const raw = event.target.value.trim();
          if (raw === "") return onChange(null);

          const parsed = Number(raw);
          onChange(Number.isFinite(parsed) ? parsed : null);
        }}
        className="h-9 w-28 rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground"
      />
    </label>
  );
}

const statusOptions: MatchStatus[] = ["scheduled", "live", "finished", "postponed"];

export function StatusFilter({
  value,
  onChange,
}: {
  value: MatchStatus | "all";
  onChange: (value: MatchStatus | "all") => void;
}) {
  return (
    <SelectFilter
      label="Statut"
      value={value}
      onChange={(next) => onChange(next as MatchStatus | "all")}
    >
      <option value="all">Tous</option>
      {statusOptions.map((status) => (
        <option key={status} value={status}>
          {matchStatusLabels[status]}
        </option>
      ))}
    </SelectFilter>
  );
}
