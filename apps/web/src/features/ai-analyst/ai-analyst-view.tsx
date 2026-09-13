"use client";

import { AiExplanation } from "@/components/domain/ai-explanation";
import { ConfidenceBadge } from "@/components/domain/confidence-badge";
import { DataModeNotice } from "@/components/domain/data-mode-notice";
import { DataQualityPanel } from "@/components/domain/data-quality-panel";
import { EmptyState } from "@/components/domain/empty-state";
import { SelectFilter } from "@/components/domain/filters";
import { ModelOutlook } from "@/components/domain/model-outlook";
import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { RisksList } from "@/components/domain/risks-list";
import { StrengthsList } from "@/components/domain/strengths-list";
import { ValueInformation } from "@/components/domain/value-information";
import { Card, CardBody } from "@/components/ui/card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { isDataSourceError } from "@/lib/api/errors";
import { footballMatchOptions } from "@/lib/football/match-options";
import { FOOTBALL_PATHS, P1_SPORT } from "@/lib/football/routes";
import { useFootballMatchId } from "@/lib/football/use-match-id";
import { formatKickoffOrUnknown, formatMatchup } from "@/lib/format/identity";
import { pageMeta } from "@/lib/navigation";
import { useFootballAiAnalyst, useFootballAiPicks, useMatches } from "@/lib/query/hooks";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

const meta = pageMeta[FOOTBALL_PATHS.aiAnalyst];

export function AiAnalystView() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { matchId, pending } = useFootballMatchId();

  const query = useFootballAiAnalyst(matchId);
  const matches = useMatches({ sport: P1_SPORT });
  const picks = useFootballAiPicks({ limit: 50 });

  const options = useMemo(
    () =>
      footballMatchOptions({
        matches: matches.data?.data.items,
        picks: picks.data?.data.items,
        currentId: matchId,
      }),
    [matches.data?.data.items, picks.data?.data.items, matchId],
  );

  const onMatchChange = useCallback(
    (next: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("match_id", next);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  if (pending) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <CardSkeleton rows={5} />
      </div>
    );
  }

  if (!matchId) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <EmptyState
          title="Aucun match à expliquer"
          description="Passez un match_id dans l'URL ou attendez qu'un match football soit publié."
        />
      </div>
    );
  }

  if (query.isError && isDataSourceError(query.error) && query.error.kind === "not_found") {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <MatchPicker value={matchId} onChange={onMatchChange} options={options} />
        <EmptyState
          title="Aucune analyse disponible"
          description={query.error.message}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <MatchPicker value={matchId} onChange={onMatchChange} options={options} />

      <QueryBoundary
        query={query}
        skeleton={
          <div className="space-y-4">
            <CardSkeleton rows={3} />
            <div className="grid gap-4 lg:grid-cols-2">
              <CardSkeleton rows={5} />
              <CardSkeleton rows={5} />
            </div>
          </div>
        }
        isEmpty={(report) => report.analyst.summary.length === 0 && report.analyst.key_factors.length === 0}
        empty={{
          title: "Analyse vide",
          description: "Le moteur a répondu sans explication. Aucun texte n'est inventé pour remplir la page.",
        }}
      >
        {(report, envelope) => {
          const matchup = formatMatchup(report.home_team, report.away_team);

          return (
            <div className="space-y-5">
              <DataModeNotice dataMode={envelope.data_mode} source={report.value.source} />

              <Card>
                <CardBody className="space-y-2">
                  <p className="text-xs uppercase tracking-[0.18em] text-ai-strong">
                    Football Intelligence
                  </p>
                  <h2 className="text-2xl font-medium tracking-tight">{matchup.text}</h2>
                  <p className="text-sm text-muted">
                    {report.league} · {formatKickoffOrUnknown(report.kickoff_at)}
                  </p>
                </CardBody>
              </Card>

              <ModelOutlook report={report} />
              <AiExplanation explanation={report.analyst} />

              <div className="grid gap-4 lg:grid-cols-2">
                <StrengthsList items={report.analyst.strengths} />
                <RisksList items={report.analyst.risks} />
              </div>

              <ValueInformation report={report} />

              <div className="grid gap-4 lg:grid-cols-2">
                <ConfidenceBadge confidence={report.analyst.confidence} />
                <DataQualityPanel report={report} />
              </div>

              <p className="text-xs leading-5 text-faint">
                Rapport explicatif {report.analyst.analysis_version}, produit par{" "}
                {report.analyst.provider}. Les probabilités, l&apos;edge et l&apos;EV sont copiés
                tels quels. Ils ne constituent ni un conseil, ni une prévision du résultat, ni une
                promesse de gain.
              </p>
            </div>
          );
        }}
      </QueryBoundary>
    </div>
  );
}

function MatchPicker({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: ReadonlyArray<{ id: string; label: string }>;
}) {
  return (
    <section
      aria-label="Match analysé"
      className="rounded-2xl border border-border bg-surface px-4 py-3"
    >
      <SelectFilter label="Match" value={value} onChange={onChange}>
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </SelectFilter>
    </section>
  );
}
