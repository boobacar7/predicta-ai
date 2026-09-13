import { cn } from "@/lib/cn";
import { formatDayNumber, formatWeekday } from "@/lib/format/dates";

export function CalendarStrip({
  days,
  value,
  onChange,
}: {
  days: string[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div role="tablist" aria-label="Date" className="flex gap-2 overflow-x-auto pb-1">
      <button
        type="button"
        role="tab"
        aria-selected={value === ""}
        onClick={() => onChange("")}
        className={cn(
          "min-w-16 rounded-2xl border px-3 py-2 text-center",
          value === ""
            ? "border-ai/40 bg-ai-soft text-foreground"
            : "border-border bg-surface text-muted hover:bg-surface-hover",
        )}
      >
        <span className="block text-[10px] uppercase tracking-[0.16em]">Dates</span>
        <span className="mt-1 block text-sm font-medium">Toutes</span>
      </button>
      {days.map((day) => {
        const iso = `${day}T12:00:00.000Z`;
        const selected = day === value;
        return (
          <button
            key={day}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(day)}
            className={cn(
              "min-w-16 rounded-2xl border px-3 py-2 text-center",
              selected
                ? "border-ai/40 bg-ai-soft text-foreground"
                : "border-border bg-surface text-muted hover:bg-surface-hover",
            )}
          >
            <span className="block text-[10px] uppercase tracking-[0.16em]">
              {formatWeekday(iso)}
            </span>
            <span className="mt-1 block font-mono text-lg tabular">{formatDayNumber(iso)}</span>
          </button>
        );
      })}
    </div>
  );
}
