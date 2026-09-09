import type { SportFilterValue } from "@/lib/filters/context";
import type {
  AvailabilityStatus,
  DashboardSnapshot,
  Insight,
  MatchSummary,
  ModelHealthSummary,
  Pick,
  ValueOpportunity,
} from "@/types/api";

/**
 * Presentation selectors for the dashboard.
 *
 * The dashboard endpoint returns a whole-day snapshot with no filter parameters,
 * so narrowing by sport happens client side. Keeping it here rather than in JSX
 * makes the rule testable and keeps the view purely declarative. Nothing in this
 * module derives a new sporting figure; it only selects and counts what the data
 * source already published.
 */

export interface FreshnessSummary {
  counts: Readonly<Record<AvailabilityStatus, number>>;
  total: number;
  /** True when at least one item is stale, partial or unavailable. */
  degraded: boolean;
}

export interface DashboardViewModel {
  headline: string;
  matches: MatchSummary[];
  picks: Pick[];
  valueOpportunities: ValueOpportunity[];
  insights: Insight[];
  modelHealth: ModelHealthSummary;
  freshness: FreshnessSummary;
}

export function matchesSport(sport: string, filter: SportFilterValue): boolean {
  return filter === "all" || filter === sport;
}

export function summarizeFreshness(matches: readonly MatchSummary[]): FreshnessSummary {
  const counts: Record<AvailabilityStatus, number> = {
    available: 0,
    unavailable: 0,
    partial: 0,
    stale: 0,
  };

  for (const match of matches) {
    counts[match.quality.availability] += 1;
  }

  return {
    counts,
    total: matches.length,
    degraded: counts.stale + counts.partial + counts.unavailable > 0,
  };
}

export function selectDashboard(
  snapshot: DashboardSnapshot,
  sport: SportFilterValue,
): DashboardViewModel {
  const matches = snapshot.matches_today.filter((match) => matchesSport(match.sport, sport));

  return {
    headline: snapshot.headline,
    matches,
    picks: snapshot.picks.filter((pick) => matchesSport(pick.match.sport, sport)),
    valueOpportunities: snapshot.value_opportunities.filter((item) =>
      matchesSport(item.match.sport, sport),
    ),
    insights: snapshot.insights,
    modelHealth: snapshot.model_health,
    freshness: summarizeFreshness(matches),
  };
}
