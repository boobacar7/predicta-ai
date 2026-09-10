# ADR 0005 — Fournisseurs V1 validés

- Statut : accepté
- Date : 2026-09-10
- Décideur : propriétaire produit
- Portée : choix de sources pour la V1 football + cotes. Aucune souscription, clé ou
  appel API n'est autorisé par cet ADR. La connexion reste un pas ultérieur,
  explicite, avec secrets hors Git.

## Contexte

L'ADR [0004](0004-data-foundation.md) avait laissé les fournisseurs en
recommandation. Le comparatif est dans [data-providers.md](../data-providers.md).
Le 10 septembre 2026, les choix V1 ont été validés avec une modification de plan
Sportmonks.

## Décisions

### Football live / stats

**Sportmonks, plan Growth** (pas Pro, pas Starter).

Growth (~99 €/mois, ~30 ligues selon l'offre 2026) suffit au périmètre ligues V1.
Le Starter (5 ligues) est trop étroit. Le Pro (~249 €/mois) est reporté tant que
Growth couvre les six compétitions retenues et la profondeur stats utile.

Recours si Growth s'avère insuffisant (stats manquantes, xG absent, quota) :
monter en Pro, ou API-Football en filet.

### Cotes

**The Odds API**, provider cotes séparé des stats.

Live / pre-match et historique PIT depuis juin 2020. Les cotes Sportmonks ne
sont pas la vérité du Value Engine. Bookmaker de référence à documenter à
l'ingestion (Pinnacle closing lorsqu'il est réellement disponible, sinon
snapshot identifié).

### Ligues football V1

1. Premier League
2. La Liga
3. Bundesliga
4. Serie A
5. Ligue 1
6. UEFA Champions League

Hors V1 : Europa League, Championship, autres championnats.

### Football historique / backtest

**football-data.co.uk** est autorisé **uniquement pour recherche et backtest**,
tant que les droits d'usage commercial produit ne sont pas explicitement validés.

Ces CSV ne doivent pas alimenter l'API produit, ni être exposés avec
`data_mode=live`, ni être présentés comme un flux PREDICTA commercial. Un
entraînement interne de recherche peut les utiliser s'il est étiqueté comme
tel. Un backtest publié dans le produit SaaS exige une validation licence
supplémentaire.

Le backfill Sportmonks sur les ligues V1 reste la voie historique **produit**
lorsque le plan Growth le permet.

### Reporté

- Basketball (BALLDONTLIE, phase 8)
- Tennis (Sackmann / live, phase 9)
- Event-level football (StatsBomb commercial ; Open Data interdit en SaaS)

### Stockage raw

- Développement : filesystem immuable (`RawStore`)
- Production : store S3-compatible, choix cloud toujours différé

### Toujours interdit sans nouvelle validation

- Scraping
- Clés API dans Git
- Connexion live sans activation explicite
- Copie des « predictions » d'un provider dans `predictions`
- StatsBomb Open Data dans le produit payant

## Conséquences

- Le prochain pas DATA est un adapter Sportmonks Growth **ou** The Odds API,
  après création des comptes et injection des secrets en environnement local,
  pas dans le dépôt.
- L'agent ML V1 vise football, ligues listées ci-dessus, features point-in-time.
  Il n'attend pas basketball, tennis ni event streams.
- Un écart Growth (ligue C1 incomplète, stats absentes) déclenche une revue de
  plan, pas un élargissement silencieux du catalogue.

## Suivi

Restent ouverts :

- lecture contractuelle Sportmonks Growth (ligues exactes, historique, xG)
- plan The Odds API (crédits historical, régions)
- licence commerciale football-data.co.uk
- bookmaker de référence figé dans le Value Engine
- compte et région S3
