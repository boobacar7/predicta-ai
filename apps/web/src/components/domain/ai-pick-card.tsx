"use client";

import { ModelStatusBadge } from "@/components/domain/model-status";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { StatTile } from "@/components/ui/stat-tile";
import { formatAbsolute } from "@/lib/format/dates";
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
 * Match identity is limited to `match_id` and `league` because the engine
 * publishes nothing else. Team names and kickoff are marked unavailable rather
 * than guessed.
 */
export function AiPickCard({ pick, onOpenDetail }: { pick: AiPick; onOpenDetail?: () => void }) {
  const headingId = `pick-${pick.match_id}-${pick.selection}`;

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
              {pick.market} · {football1x2Labels[pick.selection]}
            </h3>
            <p className="mt-1 font-mono text-xs break-all text-faint">{pick.match_id}</p>
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
          {onOpenDetail ? (
            <button
              type="button"
              onClick={onOpenDetail}
              className="text-sm text-ai-strong hover:underline"
            >
              Détail de l&apos;opportunité
            </button>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}
