"use client";

import { DataFreshness, Provenance } from "@/components/domain/data-freshness";
import { Unavailable } from "@/components/domain/unavailable";
import { DialogContent, DialogRoot } from "@/components/ui/dialog";
import { StatTile } from "@/components/ui/stat-tile";
import { formatAbsolute } from "@/lib/format/dates";
import {
  formatDecimalOdds,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import type { ValueOpportunity } from "@/types/api";
import type { ReactNode } from "react";

/**
 * Detail of one value opportunity, split along the pipeline: Prediction, Odds,
 * Value. Mirrors `AiPickDetailDialog` so both surfaces read the same way.
 *
 * Every ratio is displayed as the Value Engine published it. Unavailable inputs
 * are named as such instead of being rendered as zero, since a missing odds
 * snapshot and a zero edge are different statements.
 */
export function ValueDetailDialog({
  opportunity,
  onClose,
}: {
  opportunity: ValueOpportunity | null;
  onClose: () => void;
}) {
  return (
    <DialogRoot
      open={opportunity !== null}
      onOpenChange={(open) => (open ? undefined : onClose())}
    >
      {opportunity ? (
        <DialogContent
          title={`${opportunity.match.home.name} · ${opportunity.match.away.name}`}
        >
          <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
            <header className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-xs text-faint">{opportunity.match.league.name}</p>
                <p className="text-sm text-muted">
                  {opportunity.market} · {opportunity.selection_label}
                </p>
              </div>
              <DataFreshness quality={opportunity.quality} />
            </header>

            <Section
              title="Prediction"
              caption={
                opportunity.prediction_cutoff_at
                  ? `Probabilité calibrée au cutoff ${formatAbsolute(opportunity.prediction_cutoff_at)}.`
                  : "Cutoff de prédiction non fourni par la réponse."
              }
            >
              <StatTile
                label="P calibrée"
                value={formatProbability(opportunity.calibrated_probability)}
                tone="ai"
              />
              <StatTile label="Coup d'envoi" value={formatAbsolute(opportunity.match.kickoff_at)} />
            </Section>

            <Section
              title="Odds"
              caption={
                opportunity.odds_observed_at
                  ? `Snapshot observé le ${formatAbsolute(opportunity.odds_observed_at)}.`
                  : "Horodatage du snapshot non fourni."
              }
            >
              <StatTile label="Cote décimale" value={formatDecimalOdds(opportunity.decimal_odds)} />
              <StatTile
                label="Implicite brute"
                value={formatProbability(opportunity.implied_probability_raw)}
                hint="1 / cote"
              />
              <StatTile
                label="No-vig"
                value={formatProbability(opportunity.no_vig_probability)}
                hint="marge retirée"
              />
              <StatTile
                label="Overround"
                value={formatPoints(opportunity.overround)}
                hint="marge du marché"
              />
            </Section>

            <Section
              title="Value"
              caption={`Calculé et versionné par ${opportunity.formula_version}.`}
            >
              <StatTile label="Edge brut" value={formatPoints(opportunity.edge_raw)} />
              <StatTile
                label="Edge no-vig"
                value={formatPoints(opportunity.edge_no_vig)}
                tone="value"
              />
              <StatTile
                label="EV"
                value={formatSignedPercent(opportunity.expected_value)}
                tone="value"
              />
            </Section>

            {opportunity.quality.availability === "unavailable" ? (
              <Unavailable
                label="Analyse de value"
                reason="Aucune cote exploitable n'est associée à cette probabilité."
              />
            ) : null}

            <Provenance quality={opportunity.quality} />

            <p className="text-xs leading-5 text-faint">
              Ces ratios sont des mesures statistiques. Ils ne constituent ni un conseil, ni une
              prévision du résultat, ni une promesse de gain.
            </p>
          </div>
        </DialogContent>
      ) : null}
    </DialogRoot>
  );
}

function Section({
  title,
  caption,
  children,
}: {
  title: string;
  caption: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div>
        <h4 className="text-sm font-medium text-foreground">{title}</h4>
        <p className="text-xs text-faint">{caption}</p>
      </div>
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">{children}</dl>
    </section>
  );
}
