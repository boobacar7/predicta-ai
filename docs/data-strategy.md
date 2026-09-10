# Stratégie DATA

Ce document définit la fondation DATA de PREDICTA AI. Il ne décrit pas un fournisseur connecté ni un modèle ML. Les prédictions restent produites plus tard par l'agent ML, à partir de datasets point-in-time construits ici.

## 1. Objectif

La qualité des prédictions dépend de la qualité, de la fraîcheur et de la traçabilité des données. Le layer DATA alimente à terme football, basketball et tennis avec :

- calendrier et compétitions;
- équipes et joueurs;
- résultats;
- statistiques d'équipe et de joueur;
- événements de match;
- classements;
- blessures lorsque disponibles;
- compositions lorsque disponibles;
- cotes et historique de cotes;
- métadonnées de fraîcheur;
- identifiants fournisseurs reliés à des identifiants canoniques.

Le football est le premier périmètre d'ingestion. Basketball et tennis partagent les mêmes abstractions, avec des adapters et des champs d'extension, sans schéma universel artificiel pour les statistiques.

## 2. Principes non négociables

1. Aucune donnée fictive n'est présentée comme réelle. Toute fixture porte `data_mode=mock`.
2. Aucune cote, statistique, blessure, composition, classement ou résultat n'est inventé.
3. Une valeur absente est `null` avec `availability=unavailable`, jamais `0`.
4. Les timestamps persistés sont UTC.
5. Les payloads bruts sont immuables et séparés des entités normalisées.
6. Le domaine métier n'importe jamais un SDK fournisseur.
7. Le Data layer ne recalcule pas le Value Engine. Il fournit des snapshots de cotes propres.
8. Une feature utilisée pour un match à `T` ne peut lire que des faits disponibles avant `T`.
9. Aucune clé API n'entre dans Git. Aucun fournisseur payant n'est branché sans validation humaine.
10. Le scraping n'est pas une stratégie d'ingestion.

## 3. Architecture

```text
Provider adapter
  → raw ingestion (immuable, checksum)
  → validation
  → normalisation
  → entity resolution
  → storage (PostgreSQL canonique)
  → point-in-time features (lecture ML)
```

Les couches restent distinctes :

| Couche | Contenu | Mutabilité |
| --- | --- | --- |
| Raw | Payload provider, URI, checksum, `collected_at` | Immuable |
| Normalized | Entités canoniques, unités standardisées | Upsert idempotent |
| Curated | Observations validées, quarantaine exclue | Append-only pour les faits |
| Feature | Lectures bornées par un cutoff | Dérivée, reproductible |
| Prediction | Hors DATA ; écrite par le worker ML | Immuable une fois publiée |

PostgreSQL reste la source de vérité des entités canoniques. Le raw vit dans un store objet local (filesystem en développement, S3 plus tard) ; PostgreSQL n'en conserve que les métadonnées.

Le worker `workers/ingestion` ne crée pas une seconde base. Il écrit dans le schéma Alembic de `apps/api`.

## 4. Identité et IDs

Les IDs publics sont des chaînes stables préfixées (`spt_`, `lge_`, `tm_`, `plr_`, `mth_`, `odd_`, `raw_`, `inj_`, `lnp_`). Ils ne sont jamais égaux à un ID fournisseur.

Le mapping `provider + entity_type + provider_entity_id → canonical_id` est obligatoire. Une collision de noms ne fusionne pas silencieusement : l'enregistrement est mis en quarantaine.

## 5. Temps

Trois instants sont distingués et persistés :

| Champ | Sens |
| --- | --- |
| `event_at` | Quand le fait sportif a eu lieu (coup d'envoi, but, publication d'un classement). |
| `available_at` | Quand ce fait pouvait être connu et utilisé. C'est le garde-fou point-in-time. |
| `collected_at` | Quand PREDICTA a collecté le payload. Audit, pas filtre ML historique. |

`observed_at` exposé à l'API correspond à `available_at` lorsque les deux existent. Un backfill de résultats 2019 ingéré en 2026 doit porter `available_at` historique (fin de match + latence documentée), pas la date d'ingestion.

Pour un résultat terminé Sportmonks, `available_at` est `min(collected_at, kickoff + 3h)`, jamais antérieur au coup d'envoi. C'est une **hypothèse documentée**, pas un timestamp d'observation fourni par le provider. Si Sportmonks ne permet pas de savoir quand le résultat est devenu public, le dataset ne prétend pas un PIT parfait sur ce champ.

## 6. Point-in-time et anti-fuite

Pour prédire un match dont le coup d'envoi est `T` :

- résultats, événements et statistiques de ce match sont invisibles;
- cotes : dernier snapshot avec `available_at < T`;
- classements, blessures, compositions : uniquement si `available_at < T`;
- agrégats de forme : calculés sur les matchs `kickoff_at + duration < T` et `status=finished`.

`collected_at` ne peut pas servir de cutoff d'entraînement : il rendrait un backfill trop conservateur ou, s'il est ignoré, il masquerait une fuite. Le contrat ML est `available_at < cutoff_at` et `event_at < cutoff_at`.

Le module `predicta_ingestion.pit` refuse toute lecture qui viole ce contrat.

## 7. Historique et reproductibilité

- Cotes : table append-only `odds_snapshots` / `odds_selections`.
- Classements, blessures, compositions, statistiques : snapshots horodatés (`as_of`, `available_at`).
- Raw : conservation des payloads permettant de rejouer normalisation et mapping.
- Un dataset ML est identifié par sport, marché, `cutoff_at`, version des définitions, hash des IDs inclus et commit.

Les corrections se font par nouvel enregistrement ou quarantaine rejouable, jamais par update destructif d'un fait historique.

## 8. Cotes

Chaque snapshot conserve provider, bookmaker, marché, sélection, cote décimale (`Decimal` > 1), match canonique, `available_at` et source. Aucune cote n'est interpolée. Le DATA layer ne calcule ni implied probability de référence, ni edge, ni EV : ces formules restent dans le Value Engine versionné (`value-engine-0.1`).

## 9. Qualité

Validation stricte avant écriture canonique. Enregistrements invalides → quarantaine, jamais correction silencieuse. Les métriques suivies sont complétude, fraîcheur, duplicats, anomalies de score, cotes ≤ 1, identités ambiguës et ratio mock/live.

## 10. Fournisseurs

Les choix V1 sont dans [ADR 0005](adr/0005-data-providers-v1.md) et
[data-providers.md](data-providers.md).

- Football live / stats : Sportmonks **Growth**
- Cotes : The Odds API
- Ligues : MLS (priorité historique), Premier League, La Liga, Bundesliga, Serie A, Ligue 1, Champions League
- football-data.co.uk : recherche / backtest seulement, pas le produit, tant que la licence commerciale n'est pas explicite
- Basketball, tennis, event-level : reportés
- Raw : filesystem en développement, S3 plus tard

Aucun adapter live n'effectue d'appel réseau tant que `PREDICTA_INGESTION_ENABLE_LIVE` n'est pas activé **et** que les secrets ne sont injectés que par l'environnement.

L'adapter **Sportmonks Football** (MLS + ligues V1 + fixtures + découverte de saisons) est implémenté. Il refuse
de tourner si le live n'est pas activé ou si `SPORTMONKS_API_TOKEN` est vide.
Il ne retombe jamais sur les fixtures mock. The Odds API reste non branché.

L'historique n'est **pas** une profondeur garantie. Le pipeline découvre les saisons
que Sportmonks retourne réellement, les documente dans le rapport d'ingestion, et
n'invente aucune saison manquante. La MLS est la compétition historique de référence ;
les ligues européennes V1 sont limitées par défaut aux 3 saisons les plus récentes
sauf `--season` / `--all-seasons`.

Le dataset ML se construit via `PointInTimeStore` ; voir [ml-dataset.md](ml-dataset.md).

Guide de lancement : [workers/ingestion/README.md](../workers/ingestion/README.md).

## 11. Ordre de construction

1. Abstractions, schémas, PIT, mocks et tests.
2. Validation humaine des fournisseurs V1 (**faite**, ADR 0005).
3. Branchement contrôlé de l'adapter Sportmonks Growth (secrets hors Git).
4. Backfill football historique produit via Sportmonks (MLS d'abord, puis ligues européennes V1).
5. Construction d'un dataset ML 1X2 point-in-time (`predicta_ingestion.ml`). Aucun entraînement de modèle dans DATA.
6. Ingestion récurrente pre-match.
7. The Odds API, puis basketball, puis tennis, sur les mêmes contrats.

## 12. Hors périmètre

- modèles ML, ensemble, calibration (prochaine phase, football ligues V1);
- scraping;
- connexion payante automatique sans `PREDICTA_INGESTION_ENABLE_LIVE=true` et token local;
- calcul Value Engine;
- authentification utilisateur;
- usage produit de football-data.co.uk avant licence commerciale explicite.
