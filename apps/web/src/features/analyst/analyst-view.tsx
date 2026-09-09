"use client";

import { ErrorState } from "@/components/domain/empty-state";
import { PageHeader } from "@/components/domain/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { CardSkeleton } from "@/components/ui/skeleton";
import { defaultAnalystMatchId } from "@/data/mock/analyst";
import { pageMeta } from "@/lib/navigation";
import { useAnalystSession, useMatches } from "@/lib/query/hooks";
import { useState } from "react";

export function AnalystView() {
  const [matchId, setMatchId] = useState(defaultAnalystMatchId);
  const [question, setQuestion] = useState("Quels faits expliquent la probabilité calibrée ?");
  const [submitted, setSubmitted] = useState(question);
  const matches = useMatches({ sport: "all" }, "success");
  const session = useAnalystSession(matchId, submitted);
  const meta = pageMeta["/analyst"];

  if (matches.isError) {
    return <ErrorState description={matches.error?.message ?? "Réponse mock indisponible."} onRetry={() => void matches.refetch()} />;
  }

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
        <label className="text-sm text-muted">
          Match
          <select
            className="mt-1 h-10 w-full rounded-xl border border-border bg-surface-elevated px-3 text-foreground"
            value={matchId}
            onChange={(event) => setMatchId(event.target.value)}
          >
            {(matches.data?.data.items ?? []).map((match) => (
              <option key={match.id} value={match.id}>
                {match.home.short_name} · {match.away.short_name}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-muted">
          Question
          <Input
            className="mt-1"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
        </label>
        <Button type="submit" variant="primary" className="self-end">
          Analyser
        </Button>
      </form>
      {session.isLoading ? (
        <CardSkeleton rows={6} />
      ) : session.isError || !session.data ? (
        <ErrorState description={session.error?.message ?? "Réponse mock indisponible."} onRetry={() => void session.refetch()} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-3">
            {session.data.data.messages.map((message) => (
              <Card key={message.id}>
                <CardBody>
                  <p className="text-xs uppercase tracking-[0.16em] text-faint">
                    {message.role === "analyst" ? "Analyste" : "Vous"}
                  </p>
                  <p className="mt-2 text-sm leading-7 text-muted-strong">{message.body}</p>
                </CardBody>
              </Card>
            ))}
            <p className="text-xs text-faint">{session.data.data.disclaimer}</p>
            <p className="text-xs text-faint">
              {session.data.data.llm_model} · prompt {session.data.data.prompt_version}
            </p>
          </div>
          <Card>
            <CardBody className="space-y-3">
              <h2 className="text-sm font-medium">Fact pack {session.data.data.fact_pack.id}</h2>
              <ul className="space-y-2">
                {session.data.data.fact_pack.facts.map((fact) => (
                  <li key={fact.id} className="rounded-xl bg-surface-elevated px-3 py-2 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span>{fact.label}</span>
                      <Badge tone={fact.availability === "available" ? "muted" : "warning"}>
                        {fact.availability}
                      </Badge>
                    </div>
                    <p className="mt-1 font-mono text-muted">
                      {fact.availability === "unavailable" ? "Indisponible" : fact.value}
                    </p>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}
