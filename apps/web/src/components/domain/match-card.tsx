import { AIConfidence } from "@/components/domain/ai-confidence";
import { ProbabilityBar } from "@/components/domain/probability-bar";
import { TeamLogo } from "@/components/domain/team-logo";
import { ValueBadge } from "@/components/domain/value-badge";
import { Badge } from "@/components/ui/badge";
import { isCataloguePrototypeModel } from "@/lib/football/catalogue";
import { footballMatchPath } from "@/lib/football/routes";
import { formatClock, formatKickoff } from "@/lib/format/dates";
import { matchStatusLabels, sportLabels } from "@/lib/format/labels";
import { formatProbability, formatScore } from "@/lib/format/numbers";
import type { MatchSummary } from "@/types/api";
import Link from "next/link";

export function MatchCard({ match }: { match: MatchSummary }) {
  const live = match.status === "live";
  const outcomes = match.prediction_preview?.outcomes ?? [];
  const prototype = isCataloguePrototypeModel(match.prediction_preview?.model_version);

  return (
    <Link
      href={footballMatchPath(match.id)}
      className="block rounded-2xl border border-border bg-surface p-5 shadow-[var(--shadow-card)] transition-colors hover:border-border-strong hover:bg-surface-elevated"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs uppercase tracking-[0.16em] text-faint">
          {sportLabels[match.sport]} · {match.league.name}
        </p>
        <div className="flex items-center gap-2">
          <Badge tone={live ? "risk" : match.status === "postponed" ? "warning" : "muted"}>
            {live ? `Live · ${formatClock(match.kickoff_at)}` : matchStatusLabels[match.status]}
          </Badge>
          {!live ? <span className="text-xs text-muted">{formatKickoff(match.kickoff_at)}</span> : null}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <TeamBlock name={match.home.name} abbreviation={match.home.abbreviation} align="left" />
        <div className="text-center">
          {match.status === "finished" || live ? (
            <p className="font-mono text-2xl tabular">
              {formatScore(match.score.home)} – {formatScore(match.score.away)}
            </p>
          ) : (
            <p className="text-xs text-faint">vs</p>
          )}
        </div>
        <TeamBlock name={match.away.name} abbreviation={match.away.abbreviation} align="right" />
      </div>

      <div className="mt-5 space-y-3">
        {prototype ? (
          <div className="space-y-2">
            <Badge tone="muted">Prototype</Badge>
            <p className="text-sm text-muted">
              Catalogue de navigation. {match.prediction_preview?.model_version} n&apos;est pas le
              moteur football.
            </p>
          </div>
        ) : match.prediction_preview ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <AIConfidence level={match.prediction_preview.confidence} />
              <span className="text-xs text-muted">
                Tête {formatProbability(match.prediction_preview.leading_probability)} ·{" "}
                {match.prediction_preview.model_version}
              </span>
            </div>
            {outcomes.length > 0 ? <ProbabilityBar outcomes={outcomes} /> : null}
          </>
        ) : (
          <p className="text-sm text-muted">Prédiction indisponible pour ce match.</p>
        )}
        {prototype ? null : match.value_preview ? <ValueBadge preview={match.value_preview} /> : null}
      </div>
    </Link>
  );
}

function TeamBlock({
  name,
  abbreviation,
  align,
}: {
  name: string;
  abbreviation: string;
  align: "left" | "right";
}) {
  return (
    <div className={`flex items-center gap-3 ${align === "right" ? "flex-row-reverse text-right" : ""}`}>
      <TeamLogo name={name} abbreviation={abbreviation} />
      <p className="text-sm font-medium leading-tight">{name}</p>
    </div>
  );
}

