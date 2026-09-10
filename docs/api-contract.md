# Contrat API v1

## Autorité

[`contracts/openapi.yaml`](../contracts/openapi.yaml) est la source canonique des routes, paramètres et schémas HTTP. Ce document explique les décisions; en cas de divergence, OpenAPI prévaut.

Le préfixe est défini par le serveur OpenAPI `/api/v1`. Ainsi, le chemin OpenAPI `/dashboard` représente bien `GET /api/v1/dashboard`.

## Opérations couvertes

| Méthode | Route | Besoin frontend |
| --- | --- | --- |
| GET | `/api/v1/dashboard` | snapshot agrégé du dashboard |
| GET | `/api/v1/sports` | sports supportés et filtres |
| GET | `/api/v1/leagues` | catalogue des ligues |
| GET | `/api/v1/leagues/{league_id}` | ligue, classement et matchs récents |
| GET | `/api/v1/teams` | catalogue des équipes |
| GET | `/api/v1/teams/{team_id}` | profil, statistiques et matchs d'une équipe |
| GET | `/api/v1/players` | catalogue des joueurs |
| GET | `/api/v1/players/{player_id}` | profil et statistiques d'un joueur |
| GET | `/api/v1/matches` | calendrier filtré |
| GET | `/api/v1/matches/{match_id}` | agrégat de détail consommé par le frontend |
| GET | `/api/v1/matches/{match_id}/stats` | sous-ressource canonique de statistiques |
| GET | `/api/v1/matches/{match_id}/odds` | dernier snapshot de cotes compatible |
| GET | `/api/v1/matches/{match_id}/prediction` | prédiction publiée et calibrée |
| GET | `/api/v1/football/predictions/{match_id}` | probabilités 1X2 du modèle football versionné (`candidate`) |
| GET | `/api/v1/football/value/{match_id}` | analyse PIT odds + value du marché football 1X2 |
| GET | `/api/v1/football/ai-picks` | opportunités 1X2 filtrées et classées déterministement |
| GET | `/api/v1/picks` | signaux modèle publiés |
| GET | `/api/v1/value` | évaluations value déterministes |
| GET | `/api/v1/performance` | santé, séries et calibration du modèle |
| POST | `/api/v1/ai/analyze` | explication fondée sur un fact pack |

Le détail d'un match embarque actuellement `stats`, `odds` et `prediction` afin d'éviter plusieurs allers-retours dans les vues existantes. Les sous-ressources utilisent les mêmes DTO backend; elles ne doivent pas être calculées différemment.

`GET /football/value/{match_id}` est le contrat backend strict du Value Engine
0.1. Il appelle le Prediction Service existant, puis choisit le dernier
snapshot de cotes complet tel que `available_at <= cutoff_at`. Sa réponse
distingue les probabilités modèle, les cotes décimales, les probabilités
implicites brutes et no-vig, puis `edge` et `ev`. Elle expose les versions du
modèle, du dataset, du schéma de features et du moteur, ainsi que la source des
cotes et le `data_mode`. Voir
[`value-engine-v0.1.md`](value-engine/value-engine-v0.1.md).

## Enveloppe

Toute réponse réussie contient :

```json
{
  "data_mode": "live",
  "generated_at": "2026-09-09T18:00:00Z",
  "request_id": "req_...",
  "data": {}
}
```

- `data_mode: mock` signifie que le payload est explicitement fictif.
- `data_mode: live` signifie qu'il provient des sources réelles configurées; le terme ne décrit pas le statut live d'un match.
- Le mode `hybrid` appartient uniquement à la factory frontend qui combine plusieurs requêtes. Il n'est jamais une valeur d'enveloppe.
- `generated_at` est un timestamp RFC 3339.
- `request_id` est identique au header `X-Request-ID`.

## Disponibilité et fraîcheur

Les objets data-driven portent `DataQuality` :

- `availability`: `available`, `unavailable`, `partial` ou `stale`;
- `source`: identifiant de provider, modèle, registre ou fixture, nullable;
- `observed_at`: date d'observation, nullable;
- `freshness`: `fresh`, `acceptable` ou `stale`, nullable;
- `note`: explication humaine nullable.

`availability` répond à « la valeur est-elle utilisable ? »; `freshness` répond à « de quand date-t-elle ? ». Une valeur indisponible est `null`, jamais `0`. Les tableaux vides signifient qu'aucun élément n'est disponible; `unavailable_fields` explique les sections attendues mais absentes.

## Nullable et optional

- Les filtres HTTP sont optionnels.
- Les champs de réponse attendus sont requis pour stabiliser la génération de types.
- Un champ dont la valeur peut manquer est requis mais explicitement nullable.
- Un champ omis et un champ `null` n'ont donc pas la même sémantique.
- La question de l'analyste est envoyée comme `string | null`; le frontend transmet actuellement `null` lorsqu'elle est absente.

## Filtres et pagination

Les catalogues utilisent `sport` et `query`. Les matchs, picks et value utilisent `sport`, `league_id`, `date` et `status`. La pseudo-valeur frontend `all` n'est jamais envoyée et n'appartient pas aux enums API.

La v1 conserve la forme déjà consommée :

```json
{
  "items": [],
  "total": 0
}
```

`limit` et `offset` sont optionnels, avec bornes documentées. Cette pagination est adaptée aux catalogues et listes opérationnelles actuels. Une future ressource historique à fort volume utilisera un curseur dans un schéma distinct; elle ne changera pas silencieusement `ListResult`.

## Nombres

- Probabilités, accuracy, Brier et ECE : ratio entre `0` et `1`.
- `0.68` représente 68 %, sans arrondi côté API.
- Cote décimale : nombre strictement supérieur à `1`, ou `null`.
- Overround : ratio positif ou nul.
- Edge : différence de probabilités dans `[-1, 1]`.
- EV : `(calibrated_probability * decimal_odds) - 1`, minimum `-1`.
- Dans `FootballValueMarket`, `overround` est la somme des probabilités
  implicites brutes utilisée comme dénominateur no-vig. La marge conventionnelle
  serait `overround - 1`.
- ROI théorique : ratio de backtest, minimum `-1`; jamais une promesse.
- `theoretical_max_drawdown` : ratio non positif dans `[-1, 0]`; `-0.084` représente une baisse maximale théorique de 8,4 %.
- Les comptes sont des entiers positifs ou nuls.

Le backend doit conserver une précision suffisante pour les calculs et ne formater en pourcentage ni en devise dans le contrat.

## Erreurs

Les erreurs utilisent `application/problem+json` et RFC 9457 :

- `type`, `title`, `status`, `detail` et `request_id` requis;
- `instance` nullable;
- `X-Request-ID` répété en header;
- `404` pour une entité inconnue;
- `422` pour un body invalide;
- autres erreurs documentées par la réponse Problem commune.

Les messages ne doivent contenir ni secret, ni payload provider sensible, ni contenu de prompt privé.

## Génération TypeScript

Les noms des composants OpenAPI correspondent aux concepts de `apps/web/src/types/api.ts`. Une vérification de génération peut être exécutée sans modifier le frontend :

```bash
npx --yes openapi-typescript contracts/openapi.yaml --output /tmp/predicta-api.generated.ts
```

Lors du handoff frontend suivant, `src/types/api.ts` pourra être remplacé par la sortie générée ou par des alias nommés vers `components["schemas"]`. Ce remplacement doit être fait dans une PR frontend dédiée, avec typecheck et tests; il n'est pas nécessaire pour que le backend implémente la v1.

## Décisions de compatibilité

- `GET /dashboard` est accepté comme agrégat explicite et cacheable.
- `ModelHealthSummary.theoretical_max_drawdown` est requis et précisément borné.
- `MetricPoint` et `IdentifiedEntity` restent définis pour couvrir les types frontend partagés, même s'ils ne sont pas encore retournés seuls.
- Les marchés et sélections restent des chaînes contrôlées par le domaine plutôt qu'un enum global : les valeurs diffèrent par sport et évolueront sans version majeure.
- L'API ne définit aucun résultat comme garanti et ne délègue aucun calcul de probabilité au LLM.
