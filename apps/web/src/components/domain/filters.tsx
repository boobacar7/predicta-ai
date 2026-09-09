import { sportLabels } from "@/lib/format/labels";
import type { SportCode } from "@/types/api";
import type { SportFilterValue } from "@/lib/filters/context";
import { cn } from "@/lib/cn";

const options: Array<{ value: SportFilterValue; label: string }> = [
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
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={cn(
            "h-8 rounded-full px-3 text-xs font-medium",
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

export function LeagueFilter({
  leagues,
  value,
  onChange,
}: {
  leagues: Array<{ id: string; name: string; sport: SportCode }>;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-muted">
      Compétition
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-xl border border-border bg-surface-elevated px-3 text-foreground"
      >
        <option value="all">Toutes</option>
        {leagues.map((league) => (
          <option key={league.id} value={league.id}>
            {league.name}
          </option>
        ))}
      </select>
    </label>
  );
}
