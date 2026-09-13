import { isDataSourceError } from "@/lib/api/errors";
import { isCataloguePrototypeModel } from "@/lib/football/catalogue";
import type { MatchStatus } from "@/types/api";

/**
 * Whether Match Center / match details may call `GET /football/predictions`.
 *
 * The candidate artefact is a pre-match 1X2. Finished and postponed matches
 * must not load that estimate. Catalogue `fb-ens-*` rows are navigation
 * prototypes, not the football engine, so they must not hit the engine either.
 */
export function shouldFetchFootballPrediction(args: {
  status: MatchStatus;
  catalogueModelVersion?: string | null;
}): boolean {
  if (isCataloguePrototypeModel(args.catalogueModelVersion)) {
    return false;
  }

  return args.status === "scheduled" || args.status === "live";
}

/**
 * The engine published no prediction for this match.
 *
 * 404 is a missing row. 422 is PIT / validation refusal (`pit-features-unavailable`).
 * Both are an honest “indisponible”, not a transport failure to retry.
 */
export function isFootballPredictionUnavailable(error: unknown): boolean {
  if (!isDataSourceError(error)) {
    return false;
  }

  if (error.kind === "not_found") {
    return true;
  }

  return error.status === 422;
}
