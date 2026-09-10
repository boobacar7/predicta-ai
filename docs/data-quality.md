# Qualité des données

## 1. Disponibilité vs fraîcheur

Aligné sur le contrat API `DataQuality` :

- `availability` : la valeur est-elle utilisable ? `available` | `unavailable` | `partial` | `stale`
- `freshness` : de quand date-t-elle ? `fresh` | `acceptable` | `stale` | `null` si indisponible

Une statistique manquante n'est pas écrite à `0`. Une liste vide signifie « aucun élément disponible », distinct d'une erreur provider.

## 2. Politique de fraîcheur (v1)

Seuils par ressource, comparés à `now - available_at` pour les flux opérationnels. L'historique terminé n'est pas jugé stale.

| Ressource | fresh | acceptable | ensuite |
| --- | --- | --- | --- |
| Cotes pre-match | ≤ 15 min | ≤ 2 h | stale |
| Cotes live | ≤ 30 s | ≤ 2 min | stale |
| Calendrier / statuts | ≤ 5 min | ≤ 30 min | stale |
| Classements | ≤ 6 h | ≤ 24 h | stale |
| Blessures | ≤ 6 h | ≤ 24 h | stale |
| Compositions confirmées | ≤ 60 min avant kickoff | jusqu'au kickoff | stale ou unused post-kickoff |
| Résultat terminé | n/a (immuable) | — | — |

Ces seuils sont des constantes nommées dans `predicta_ingestion.quality.freshness`. Ils ne sont pas magiques dans les adapters.

Une cote stale peut rester stockée (historique) mais le Value Engine devra la refuser selon sa propre politique. Le DATA layer ne supprime pas l'historique stale.

## 3. Contrôles de validation

| Contrôle | Action si échec |
| --- | --- |
| JSON parseable | quarantaine `invalid_json` |
| Timestamps timezone-aware → UTC | quarantaine `naive_datetime` |
| Cote `Decimal > 1` | quarantaine `invalid_odds` |
| IDs provider non vides | quarantaine `missing_provider_id` |
| Sport ∈ {football, basketball, tennis} | quarantaine `unknown_sport` |
| Mapping statut de match | quarantaine `unknown_status` |
| `data_mode` cohérent avec la source | rejet du run si live revendiqué sur fixture |
| Taille de payload | rejet `payload_too_large` |
| Somme des scores incohérente avec événements (lorsque les deux existent) | quarantaine `inconsistent_score` |

Aucune correction automatique (ex. inverser domicile/extérieur, clipper une cote à 1.01).

## 4. Quarantaine

Table `quarantine_records` : raison, provider, identifiant provider, extrait non secret, `raw_payload_id`, run id. Les enregistrements quarantinés ne sont pas visibles du `PointInTimeStore`.

Un replay après correction de mapping produit un nouvel ingest ; le raw d'origine reste.

## 5. Déduplication et idempotence

Rejouer le même payload (même checksum) ne crée pas de nouvelle entité. Un snapshot de cotes au même `(provider, bookmaker, match, market, available_at)` est un no-op.

## 6. Mocks vs réel

- Fixtures : `workers/ingestion/fixtures/`, toujours `data_mode=mock`.
- Fixtures API FastAPI : `apps/api/app/fixtures`, déjà mock.
- Fixtures frontend : `apps/web/src/data/mock`.

Un entraînement, un backtest ou une page produit ne doivent jamais mélanger ces jeux sans le déclarer. `PREDICTA_INGESTION_DATA_MODE=mock` est la valeur par défaut. La production refuse le mock, comme l'API.

## 7. Erreurs provider

| Classe | Exemple | Comportement |
| --- | --- | --- |
| `ProviderNotConfigured` | clé absente | fail fast, pas de retry infini |
| `LiveIngestionDisabled` | flag live off | fail fast |
| `ProviderRateLimited` | 429 | retry borné + jitter (non implémenté tant que live off) |
| `ProviderUnavailable` | 5xx / timeout | échec de run, pas d'entités partielles silencieuses |
| `ProviderAuthError` | 401/403 | fail fast, log sans secret |

Un run en échec laisse le raw éventuellement déjà écrit (immuable) et n'écrit pas de canonique partiel pour ce batch, sauf enregistrements déjà validés d'un lot précédent. La transaction canonique est atomique par batch.

## 8. Métriques à exposer (plus tard)

- records lus / acceptés / quarantinés par provider et ressource
- âge p50/p95 par ressource
- taux de mapping d'identités
- duplicats évités
- ratio `data_mode`

Pas de payload provider ni de clé dans les logs.

## 9. Tests de qualité exigés

Le package ingestion couvre : parsing, validation, normalisation, mapping provider → canonique, timestamps UTC, déduplication, fraîcheur, point-in-time, ingestion bout-en-bout mock, erreurs provider. Les fixtures de test ne sont jamais étiquetées `live`.
