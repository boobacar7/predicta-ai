import { Unavailable } from "@/components/domain/unavailable";
import type { MatchEvent } from "@/types/api";

export function MatchTimeline({ events }: { events: MatchEvent[] }) {
  if (events.length === 0) {
    return (
      <Unavailable
        label="Chronologie"
        reason="Aucun événement n'est publié pour ce match mock."
      />
    );
  }

  return (
    <ol className="space-y-3">
      {events.map((event) => (
        <li key={event.id} className="flex gap-3 text-sm">
          <span className="w-10 font-mono text-muted tabular">
            {event.minute === null ? "—" : `${event.minute}'`}
          </span>
          <span>{event.label}</span>
        </li>
      ))}
    </ol>
  );
}
