"use client";

import { ErrorState } from "@/components/domain/empty-state";
import { FootballPredictionPanel } from "@/components/domain/football-prediction-panel";
import { Unavailable } from "@/components/domain/unavailable";
import { Skeleton } from "@/components/ui/skeleton";
import { isFootballPredictionUnavailable } from "@/lib/football/prediction-query";
import { useFootballPrediction } from "@/lib/query/hooks";

const UNAVAILABLE_COPY = "Prédiction indisponible pour ce match.";

/**
 * Loads `GET /football/predictions/{match_id}` and copies the published 1X2.
 *
 * When `enabled` is false the engine is not called (finished / postponed /
 * catalogue prototype). A 404 or 422 is an unpublished prediction, not a
 * transport error.
 */
export function FootballPredictionSlot({
  matchId,
  enabled,
  variant = "full",
}: {
  matchId: string;
  enabled: boolean;
  variant?: "full" | "compact";
}) {
  const query = useFootballPrediction(matchId, undefined, { enabled });
  const compact = variant === "compact";

  if (!enabled) {
    return <UnavailablePrediction compact={compact} />;
  }

  if (query.isPending) {
    return (
      <div role="status" aria-label="Chargement de la prédiction" aria-busy="true">
        {compact ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="space-y-3">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-2 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}
      </div>
    );
  }

  if (query.isError) {
    if (isFootballPredictionUnavailable(query.error)) {
      return <UnavailablePrediction compact={compact} />;
    }

    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const prediction = query.data.data;

  return <FootballPredictionPanel prediction={prediction} variant={variant} />;
}

function UnavailablePrediction({ compact }: { compact: boolean }) {
  if (compact) {
    return <p className="text-sm text-muted">{UNAVAILABLE_COPY}</p>;
  }

  return (
    <Unavailable
      label="Prédiction"
      reason="Le moteur football n'a publié aucune prédiction pour ce match."
    />
  );
}
