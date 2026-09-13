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
import {
  ANALYST_MISSING_FACTORS_ID,
  ANALYST_MISSING_IDENTITY_ID,
  ANALYST_MISSING_VALUE_ID,
  ANALYST_INVALID_KICKOFF_ID,
  LINCOLN_ANALYST_MATCH_ID,
  analystMatchOptions,
} from "@/data/mock/ai-analyst";
import { useFilters } from "@/lib/filters/context";
import { formatKickoffOrUnknown, formatMatchup } from "@/lib/format/identity";
import { isDataSourceError } from "@/lib/api/errors";
import { pageMeta } from "@/lib/navigation";
import { useFootballAiAnalyst } from "@/lib/query/hooks";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback } from "react";

const meta = pageMeta["/ai-analyst"];

const SELECTABLE_IDS = new Set<string>([
  LINCOLN_ANALYST_MATCH_ID,
  ANALYST_MISSING_IDENTITY_ID,
  ANALYST_MISSING_VALUE_ID,
  ANALYST_MISSING_FACTORS_ID,
  ANALYST_INVALID_KICKOFF_ID,
]);

export function AiAnalystView() {
  const { sport } = useFilters();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const matchId = searchParams.get("match_id") ?? LINCOLN_ANALYST_MATCH_ID;
  const engineCoversSport = sport === "all" || sport === "football";

  const query = useFootballAiAnalyst(engineCoversSport ? matchId : "");

  const onMatchChange = useCallback(
    (next: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("match_id", next);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [pathname, router, searchParams],
  );

  if (!engineCoversSport) {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <EmptyState
          title="Analyste limité au football"
          description="La version ai-analyst-0.1 n'explique que le football 1X2. Aucune analyse n'est simulée pour le sport actif."
        />
      </div>
    );
  }

  if (query.isError && isDataSourceError(query.error) && query.error.kind === "not_found") {
    return (
      <div className="space-y-6">
        <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
        <MatchPicker value={matchId} onChange={onMatchChange} />
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
      <MatchPicker value={matchId} onChange={onMatchChange} />

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

function MatchPicker({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <section
      aria-label="Match analysé"
      className="rounded-2xl border border-border bg-surface px-4 py-3"
    >
      <SelectFilter label="Match" value={value} onChange={onChange}>
        {SELECTABLE_IDS.has(value) ? null : <option value={value}>{value}</option>}
        {analystMatchOptions.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </SelectFilter>
    </section>
  );
}
