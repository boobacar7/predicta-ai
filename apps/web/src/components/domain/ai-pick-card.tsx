"use client";

import { ModelStatusBadge } from "@/components/domain/model-status";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import { formatAbsolute } from "@/lib/format/dates";
import { formatKickoffOrUnknown, formatMatchup } from "@/lib/format/identity";
import Link from "next/link";
import { football1x2Labels } from "@/lib/format/labels";
import {
  formatDecimalOdds,
  formatMetric,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import type { AiPick } from "@/types/api";

/**
 * One ranked opportunity from `ai-picks-0.1`.
 *
 * Every figure is rendered exactly as published. The card computes nothing,
 * including `opportunity_score`, which is shown rather than re-derived from
 * `ev + edge` so that a divergence with the engine stays visible instead of
 * being hidden by the UI.
 *
 * The engine publishes canonical team labels resolved from the point-in-time
 * archive, and they are nullable. When both are present the card leads with
 * the matchup; when the archive resolved none, it says so and falls back to
 * `match_id`, which is the only identifier left.
 */
export function AiPickCard({ pick, onOpenDetail }: { pick: AiPick; onOpenDetail?: () => void }) {
  const headingId = `pick-${pick.match_id}-${pick.selection}`;
  const matchup = formatMatchup(pick.home_team, pick.away_team);

  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="ai">Rang {pick.rank}</Badge>
              <p className="text-xs text-faint">{pick.league}</p>
            </div>

            <h3 id={headingId} className="mt-2 text-lg font-medium">
              {matchup.home} <span className="text-faint">vs</span> {matchup.away}
            </h3>

            <p className="mt-1 text-sm text-muted">
              {formatKickoffOrUnknown(pick.kickoff_at)} · {pick.market} ·{" "}
              {football1x2Labels[pick.selection]}
            </p>

            {matchup.resolved ? null : (
              <p className="mt-1 font-mono text-xs break-all text-faint">{pick.match_id}</p>
            )}
          </div>
          <ModelStatusBadge version={pick.model_version} status={pick.model_status} />
        </div>

        <dl aria-labelledby={headingId} className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <StatTile
            label="P modèle"
            value={formatProbability(pick.model_probability)}
            tone="ai"
          />
          <StatTile label="Cote" value={formatDecimalOdds(pick.odds)} />
          <StatTile label="Implicite" value={formatProbability(pick.implied_probability)} />
          <StatTile label="No-vig" value={formatProbability(pick.no_vig_probability)} />
          <StatTile label="Edge" value={formatPoints(pick.edge)} tone="value" />
          <StatTile label="EV" value={formatSignedPercent(pick.ev)} tone="value" />
        </dl>

        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
          <p className="text-xs text-faint">
            Score {formatMetric(pick.opportunity_score)} · cutoff {formatAbsolute(pick.cutoff_at)} ·
            cotes <span className="font-mono">{pick.odds_source}</span>
          </p>
          <div className="flex flex-wrap items-center gap-4">
            {onOpenDetail ? (
              <button
                type="button"
                onClick={onOpenDetail}
                className="text-sm text-ai-strong hover:underline"
              >
                Détail de l&apos;opportunité
              </button>
            ) : null}
            <Link
              href={`/matches/${pick.match_id}`}
              className="text-sm text-muted hover:text-foreground hover:underline"
            >
              Voir le match
            </Link>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
