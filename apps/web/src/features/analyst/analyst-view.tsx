"use client";

import { PageHeader } from "@/components/domain/page-header";
import { QueryBoundary } from "@/components/domain/query-boundary";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CardSkeleton } from "@/components/ui/skeleton";
import { defaultAnalystMatchId } from "@/data/mock/analyst";
import { formatAbsolute } from "@/lib/format/dates";
import { availabilityLabels } from "@/lib/format/labels";
import { pageMeta } from "@/lib/navigation";
import { useAnalystSession, useMatches } from "@/lib/query/hooks";
import type { AnalystMessage, Fact } from "@/types/api";
import { useState } from "react";

const meta = pageMeta["/analyst"];
const DEFAULT_QUESTION = "Quels faits expliquent la probabilité calibrée ?";

export function AnalystView() {
  const [matchId, setMatchId] = useState(defaultAnalystMatchId);
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [submitted, setSubmitted] = useState(DEFAULT_QUESTION);

  const matches = useMatches();
  const session = useAnalystSession(matchId, submitted);

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <form
        className="grid gap-3 md:grid-cols-[16rem_1fr_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitted(question);
        }}
      >
        <label className="flex flex-col gap-1 text-xs text-muted">
          Match analysé
          <select
            className="h-10 w-full rounded-xl border border-border bg-surface-elevated px-3 text-sm text-foreground disabled:opacity-50"
            value={matchId}
            disabled={matches.isPending}
            onChange={(event) => setMatchId(event.target.value)}
          >
            {(matches.data?.data.items ?? []).map((match) => (
              <option key={match.id} value={match.id}>
                {match.home.short_name} · {match.away.short_name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs text-muted">
          Question
          <Input
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Posez une question sur le contexte du match"
          />
        </label>

        <Button type="submit" variant="primary" className="self-end">
          Analyser
        </Button>
      </form>

      <QueryBoundary
        query={session}
        skeleton={
          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <CardSkeleton rows={5} />
            <CardSkeleton rows={5} />
          </div>
        }
      >
        {(analystSession) => (
          <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="space-y-3">
              {analystSession.messages.map((message) => (
                <MessageCard key={message.id} message={message} />
              ))}
              <p className="text-xs text-faint">{analystSession.disclaimer}</p>
              <p className="text-xs text-faint">
                {analystSession.llm_model} · prompt {analystSession.prompt_version} · fact pack{" "}
                {analystSession.fact_pack.id}
              </p>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Paquet de faits</CardTitle>
                <p className="text-xs text-faint">
                  Généré le {formatAbsolute(analystSession.fact_pack.generated_at)}
                </p>
              </CardHeader>
              <CardBody>
                <p className="mb-3 text-xs text-muted">
                  L&apos;analyste ne peut citer que ces faits. Il ne comble aucun champ absent et ne
                  modifie aucune probabilité.
                </p>
                {analystSession.fact_pack.facts.length === 0 ? (
                  <p className="text-sm text-muted">
                    Aucun fait validé n&apos;est disponible pour ce match.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {analystSession.fact_pack.facts.map((fact) => (
                      <FactRow key={fact.id} fact={fact} />
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>
        )}
      </QueryBoundary>
    </div>
  );
}

function MessageCard({ message }: { message: AnalystMessage }) {
  const isAnalyst = message.role === "analyst";

  return (
    <Card>
      <CardBody>
        <p className="text-xs uppercase tracking-[0.16em] text-faint">
          {isAnalyst ? "Analyste" : "Vous"}
        </p>
        <p className="mt-2 text-sm leading-7 text-muted-strong">{message.body}</p>
        {message.cited_fact_ids.length > 0 ? (
          <p className="mt-3 font-mono text-[11px] text-faint">
            Faits cités : {message.cited_fact_ids.join(", ")}
          </p>
        ) : null}
      </CardBody>
    </Card>
  );
}

function FactRow({ fact }: { fact: Fact }) {
  const unavailable = fact.availability === "unavailable";

  return (
    <li className="rounded-xl bg-surface-elevated px-3 py-2 text-xs">
      <div className="flex items-start justify-between gap-2">
        <span className="text-foreground">{fact.label}</span>
        <Badge tone={fact.availability === "available" ? "muted" : "warning"}>
          {availabilityLabels[fact.availability]}
        </Badge>
      </div>
      <p className="mt-1 font-mono text-muted">
        {unavailable ? "Indisponible" : `${fact.value}${fact.unit ? ` ${fact.unit}` : ""}`}
      </p>
      <p className="mt-1 text-[11px] text-faint">
        {fact.source} · {formatAbsolute(fact.observed_at)}
      </p>
    </li>
  );
}
