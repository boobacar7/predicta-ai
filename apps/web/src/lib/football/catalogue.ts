/**
 * Marks fictional catalogue models so they cannot be read as the football engine.
 *
 * `fb-ens-*` lives only on the Phase-1 prototype matches. The candidate engine
 * publishes `football-elo-v1-candidate`.
 */
export function isCataloguePrototypeModel(version: string | null | undefined): boolean {
  return Boolean(version?.startsWith("fb-ens-"));
}
