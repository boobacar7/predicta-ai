"use client";

import { ModelStatusBadge } from "@/components/domain/model-status";
import { Unavailable } from "@/components/domain/unavailable";
import { DialogContent, DialogRoot } from "@/components/ui/dialog";
import { StatTile } from "@/components/ui/stat-tile";
import { formatAbsolute } from "@/lib/format/dates";
import { formatKickoffOrUnknown, formatMatchup } from "@/lib/format/identity";
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
 * Match, Prediction, Odds, Value, then Metadata.
 *
 * The split is the point. It shows which service is responsible for each
 * figure, so a reader can tell an archived fact from a model estimate, from a
 * market observation, and from a derived ratio, rather than seeing one
 * undifferentiated block.
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
      {pick ? <PickDetail pick={pick} /> : null}
    </DialogRoot>
  );
}

function PickDetail({ pick }: { pick: AiPick }) {
  const matchup = formatMatchup(pick.home_team, pick.away_team);

  return (
    <DialogContent
      title={matchup.text}
    >
      <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
        <header className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-xs text-faint">{pick.league}</p>
            <p className="font-mono text-xs break-all text-muted">{pick.match_id}</p>
          </div>
          <ModelStatusBadge version={pick.model_version} status={pick.model_status} />
        </header>

        <Section
          title="Match"
          caption="Identité canonique résolue dans l'archive point-in-time, telle que publiée."
        >
          <StatTile label="Équipe à domicile" value={matchup.home} />
          <StatTile label="Équipe à l'extérieur" value={matchup.away} />
          <StatTile label="Compétition" value={pick.league} />
          <StatTile label="Coup d'envoi" value={formatKickoffOrUnknown(pick.kickoff_at)} />
        </Section>

        {matchup.resolved ? null : (
          <Unavailable
            label="Identité des équipes"
            reason="L'archive point-in-time ne fournit pas de libellé canonique pour ce match ; seul l'identifiant est publié."
          />
        )}

        <Section
          title="Prediction"
          caption={`Probabilité calibrée par ${pick.model_version}, statut ${pick.model_status}.`}
        >
          <StatTile label="P modèle" value={formatProbability(pick.model_probability)} tone="ai" />
          <StatTile label="Marché" value={pick.market} />
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
          <StatTile label="Score" value={formatMetric(pick.opportunity_score)} hint="EV + Edge" />
          <StatTile label="Rang" value={`#${pick.rank}`} />
        </Section>

        <Section title="Metadata" caption="Versions des services ayant produit cette ligne.">
          <StatTile label="Modèle" value={pick.model_version} />
          <StatTile label="Statut modèle" value={pick.model_status} />
          <StatTile label="Value Engine" value={pick.value_engine_version} />
          <StatTile label="Moteur AI Picks" value={pick.ai_picks_version} />
        </Section>

        <p className="text-xs leading-5 text-faint">
          Ces valeurs sont des mesures statistiques produites par des services versionnés. Elles ne
          constituent ni un conseil, ni une prévision du résultat, ni une promesse de gain. Réponse
          générée le {formatAbsolute(pick.generated_at)}.
        </p>
      </div>
    </DialogContent>
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
