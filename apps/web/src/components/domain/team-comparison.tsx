import { TeamLogo } from "@/components/domain/team-logo";
import { Unavailable } from "@/components/domain/unavailable";
import type { MatchStatistic, Team } from "@/types/api";

export function TeamComparison({
  home,
  away,
  stats,
}: {
  home: Team;
  away: Team;
  stats: MatchStatistic[];
}) {
  if (stats.length === 0) {
    return (
      <Unavailable
        label="Statistiques de match"
        reason="Aucun indicateur n'est publié pour cette rencontre."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm">
        <span className="flex items-center gap-2">
          <TeamLogo name={home.name} abbreviation={home.abbreviation} size="sm" />
          {home.short_name}
        </span>
        <span className="flex items-center gap-2">
          {away.short_name}
          <TeamLogo name={away.name} abbreviation={away.abbreviation} size="sm" />
        </span>
      </div>
      <ul className="space-y-4">
        {stats.map((stat) => {
          const homeValue = stat.home_value;
          const awayValue = stat.away_value;
          const unavailable = homeValue === null && awayValue === null;
          const total = (homeValue ?? 0) + (awayValue ?? 0);
          const homeShare = total === 0 ? 0.5 : (homeValue ?? 0) / total;

          return (
            <li key={stat.key}>
              <div className="mb-1 flex items-center justify-between text-xs text-muted">
                <span className="font-mono tabular">{homeValue ?? "—"}</span>
                <span>{stat.label}</span>
                <span className="font-mono tabular">{awayValue ?? "—"}</span>
              </div>
              {unavailable ? (
                <p className="text-xs text-faint">
                  {stat.quality.note ?? "Indicateur indisponible. Pas de zéro par défaut."}
                </p>
              ) : (
                <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-elevated">
                  <div className="h-full bg-home" style={{ width: `${homeShare * 100}%` }} />
                  <div className="h-full bg-away" style={{ width: `${(1 - homeShare) * 100}%` }} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
