import { AIConfidence } from "@/components/domain/ai-confidence";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody } from "@/components/ui/card";
import { footballMatchPath } from "@/lib/football/routes";
import { formatKickoff } from "@/lib/format/dates";
import { formatProbability } from "@/lib/format/numbers";
import type { Pick } from "@/types/api";
import Link from "next/link";

export function PredictionCard({ pick }: { pick: Pick }) {
  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge tone="ai">Pick · {pick.model_version}</Badge>
          <AIConfidence level={pick.confidence} />
        </div>
        <div>
          <p className="text-xs text-faint">{pick.match.league.name}</p>
          <h3 className="mt-1 text-lg font-medium tracking-tight">
            {pick.match.home.name} · {pick.match.away.name}
          </h3>
          <p className="mt-1 text-sm text-muted">{formatKickoff(pick.match.kickoff_at)}</p>
        </div>
        <p className="text-sm">
          Signal : <span className="text-foreground">{pick.selection_label}</span>
          <span className="ml-2 font-mono tabular text-ai-strong">
            {formatProbability(pick.calibrated_probability)}
          </span>
        </p>
        <p className="text-sm leading-6 text-muted">{pick.rationale}</p>
        <p className="text-xs text-faint">Critère : {pick.criteria}</p>
        <Link href={footballMatchPath(pick.match.id)} className="text-sm text-ai-strong hover:underline">
          Ouvrir le match
        </Link>
      </CardBody>
    </Card>
  );
}
