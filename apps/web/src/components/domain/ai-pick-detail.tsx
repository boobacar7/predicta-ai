"use client";

import { ModelStatusBadge } from "@/components/domain/model-status";
import { Unavailable } from "@/components/domain/unavailable";
import { DialogContent, DialogRoot } from "@/components/ui/dialog";
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
import type { ReactNode } from "react";

/**
 * Detail of one opportunity, split along the pipeline that produced it:
 * Prediction, then Odds, then Value.
 *
 * The split is the point. It shows which service is responsible for each
 * figure, so a reader can tell a model estimate from a market observation and
 * from a derived ratio, rather than seeing one undifferentiated block.
 *
 * There is no recommendation, no stake and no outcome claim.
 */
export function AiPickDetailDialog({
  pick,
  onClose,
}: {
  pick: AiPick | null;
  onClose: () => void;
}) {
  return (
    <DialogRoot open={pick !== null} onOpenChange={(open) => (open ? undefined : onClose())}>
      {pick ? (
        <DialogContent title={`${pick.market} · ${football1x2Labels[pick.selection]}`}>
          <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
            <header className="flex flex-wrap items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-xs text-faint">{pick.league}</p>
                <p className="font-mono text-xs break-all text-muted">{pick.match_id}</p>
              </div>
              <ModelStatusBadge version={pick.model_version} status={pick.model_status} />
            </header>

            <Unavailable
              label="Identité des équipes et coup d'envoi"
              reason={`Le moteur ${pick.ai_picks_version} ne publie ni nom d'équipe ni horaire ; seul l'identifiant du match est exposé.`}
            />

            <Section
              title="Prediction"
              caption={`Probabilité calibrée par ${pick.model_version}, statut ${pick.model_status}.`}
            >
              <StatTile
                label="P modèle"
                value={formatProbability(pick.model_probability)}
                tone="ai"
              />
              <StatTile label="Sélection" value={football1x2Labels[pick.selection]} />
              <StatTile label="Cutoff" value={formatAbsolute(pick.cutoff_at)} />
            </Section>

            <Section
              title="Odds"
              caption={`Snapshot horodaté de ${pick.odds_source}, retenu car disponible au cutoff.`}
            >
              <StatTile label="Cote décimale" value={formatDecimalOdds(pick.odds)} />
              <StatTile
                label="Implicite brute"
                value={formatProbability(pick.implied_probability)}
                hint="1 / cote"
              />
              <StatTile
                label="No-vig"
                value={formatProbability(pick.no_vig_probability)}
                hint="marge retirée"
              />
            </Section>

            <Section
              title="Value"
              caption={`Calculé par ${pick.value_engine_version}, puis classé par ${pick.ai_picks_version}.`}
            >
              <StatTile label="Edge" value={formatPoints(pick.edge)} tone="value" />
              <StatTile label="EV" value={formatSignedPercent(pick.ev)} tone="value" />
              <StatTile
                label="Score"
                value={formatMetric(pick.opportunity_score)}
                hint="EV + Edge"
              />
              <StatTile label="Rang" value={`#${pick.rank}`} />
            </Section>

            <p className="text-xs leading-5 text-faint">
              Ces valeurs sont des mesures statistiques produites par des services versionnés. Elles
              ne constituent ni un conseil, ni une prévision du résultat, ni une promesse de gain.
              Réponse générée le {formatAbsolute(pick.generated_at)}.
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
