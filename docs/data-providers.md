# Fournisseurs de données

Étude destinée à une **décision humaine**. Aucun fournisseur payant n'est branché. Les prix et couvertures sont ceux constatés en septembre 2026 et peuvent changer. Vérifier contrat, licence d'usage produit et droits de redistribution avant tout abonnement.

PREDICTA AI n'est pas un bookmaker. Les cotes sont des observations pour comparer une probabilité modèle à une probabilité implicite, pas un flux de tenue de marché.

## 1. Grille d'évaluation

Chaque source est jugée sur :

- couverture (sports, ligues, marchés);
- historique disponible et granularité temporelle;
- fraîcheur (pre-match, live);
- stabilité et documentation API;
- limites (quota, rate limit, daily cap);
- coût total (pas seulement l'entrée);
- licence / droits d'utilisation commerciale et redistribution;
- stabilité des identifiants;
- statistiques réellement disponibles (pas seulement listées);
- aptitude point-in-time (timestamps d'observation).

Le moins cher n'est pas retenu par défaut.

## 2. Football

### Sportmonks Football API

- **Couverture** : 2 200+ compétitions revendiquées ; stats plus homogènes que les agrégateurs bas de gamme ; xG et métriques propriétaires sur les plans adéquats.
- **Historique** : multi-saisons selon le plan ; vérifier le pack historique avant achat.
- **Fraîcheur** : livescore et fixtures ; SLA 99,99 % annoncé.
- **API** : REST documentée, support humain, limites horaires plutôt que cap journalier brutal.
- **Coût** : entrée ~29 €/mois (Starter, ligues limitées), Growth ~99 €, Pro ~249 €, Enterprise sur devis. Plus cher qu'API-Football à l'entrée.
- **Licence** : commerciale self-serve ; redistribution et usage « betting product » à relire.
- **IDs** : stables par entité ; mapping vers canonique obligatoire.
- **Stats** : équipes, joueurs, événements, lineups, classements, blessures selon endpoints ; xG non universel sur tous les plans.
- **Limite** : le Starter ne couvre pas le catalogue produit visé. Budget réel = plan Pro ou plus pour PREDICTA.

**Rôle V1 validé** : fournisseur **principal football live + stats**, plan **Growth**. Voir [ADR 0005](adr/0005-data-providers-v1.md).

### API-Football (API-Sports)

- **Couverture** : ~1 000+ ligues, surface large (fixtures, events, lineups, injuries, players, standings, odds in-play/pre-match).
- **Historique** : saisons majeures souvent depuis ~2010 ; la profondeur stats varie fortement hors top 5.
- **Fraîcheur** : livescore correct pour un prototype ; pas de SLA public comparable.
- **API** : REST très documentée, écosystème RapidAPI ; caps **journaliers** (100/j free, 7 500/j Pro ~19 $/mois).
- **Coût** : meilleur prix d'entrée. Le coût caché est la qualité hétérogène et le plafond le jour de charge.
- **Licence** : usage API ; ne pas traiter leurs « predictions » comme prédictions PREDICTA.
- **IDs** : numériques stables au sein du provider.
- **Stats** : nombreuses mais inégales ; xG limité ou absent selon compétitions.

**Rôle recommandé** : **bootstrap** et cible de parsing (fixtures mock actuelles). Candidat live seulement si le budget Sportmonks est refusé et que l'on accepte une qualité variable.

### football-data.org

- **Couverture** : ~12 compétitions majeures.
- **Historique** : utile, borné.
- **Fraîcheur** : faible (pas un live feed).
- **API** : REST propre, free forever limité (~10 req/min).
- **Coût** : gratuit / plans modestes.
- **Licence** : relire les conditions commerciales.
- **Usage** : apprentissage et filet de sécurité, **pas** le socle produit.

### football-data.co.uk (CSV)

- **Couverture** : divisions européennes historiques + d'autres championnats ; résultats et **cotes de bookmakers**.
- **Historique** : résultats ~1993+, cotes bookmakers ~2000/01, closing odds plus récents (dont Pinnacle sur une fenêtre). Profondeur exceptionnelle pour le backtest football.
- **Fraîcheur** : mises à jour quelques fois par semaine, pas live.
- **API** : **aucune**. Fichiers CSV. Ce n'est pas du scraping de site tiers opaque : ce sont des fichiers publiés par l'auteur, mais ce n'est pas un contrat SLA.
- **Coût** : gratuit.
- **Licence** : usage quantitatif annoncé ; **validation humaine obligatoire** avant usage commercial produit.
- **PIT** : closing odds ≈ information disponible au coup d'envoi, précieux. Les cotes « pre-closing » n'équivalent pas à un snapshot à `T-24h` sauf documentation contraire.
- **Stats** : limitées (corners, cartons, etc. selon saisons), pas d'événements riches ni de xG.

**Rôle V1 validé** : **archive recherche / backtest uniquement**, jusqu'à validation explicite des droits commerciaux produit. Pas d'exposition API live.

### StatsBomb Open Data

- **Couverture** : compétitions sélectionnées seulement (pas le calendrier mondial live).
- **Historique** : event-level de très haute qualité (passes, shots, lineups).
- **Fraîcheur** : dump, pas un feed opérationnel.
- **Coût** : gratuit pour le jeu ouvert.
- **Licence** : **non commercial** / recherche. Attribution obligatoire. **Interdit de propulser le produit SaaS sans licence StatsBomb commerciale.**
- **Rôle recommandé** : recherche interne éventuelle **après** confirmation juridique. Pas une source production.

### Sportradar / Stats Perform (Opta)

- **Couverture et fraîcheur** : référence entreprise, droits officiels fréquents.
- **Coût** : devis, souvent hors budget fondation (ordre de grandeur milliers €/mois).
- **Rôle recommandé** : option **phase ultérieure** si un partenaire ou un SLA officiel devient nécessaire. Pas le premier contrat.

### Non retenus comme stratégie

- Scraping Transfermarkt, SofaScore, FBref, Understat : interdit par la stratégie DATA.
- « Predictions » d'un provider : jamais copiées dans `predictions`.

## 3. Basketball

### BALLDONTLIE

- **Couverture** : NBA historique **1946 → courant**, box scores, averages, advanced stats, standings, injuries, lineups, play-by-play et odds selon palier. Extension multi-ligues (WNBA, etc.) selon offre 2026.
- **Historique** : meilleur rapport profondeur / accessibilité pour la NBA.
- **Fraîcheur** : API REST, pas un feed bookmaker officiel.
- **API** : OpenAPI, pagination curseur, clé requise.
- **Coût** : palier free limité ; payant selon endpoints (ordre dizaines à centaines $/mois selon GOAT / all-access — **à reconfirmer**).
- **Licence** : commerciale self-serve à relire (usage NBA + cotes).
- **IDs** : propres au provider ; mapping NBA standard (équipe/joueur) relativement propre.
- **Limite** : Euroleague / basketball monde non couverts au même niveau.

**Rôle recommandé** : **principal basketball (NBA)** quand la phase 8 démarre.

### API-Basketball (API-Sports)

- Même famille qu'API-Football. Utile pour **Euroleague et championnats hors NBA**. Qualité et historique à prototyper avant engagement.

### SportsDataIO / Sportradar NBA

- Profondeur entreprise, projections, odds packagés. Devis. Reporter.

## 4. Tennis

### Jeff Sackmann (`tennis_atp` / `tennis_wta`)

- **Couverture** : ATP/WTA, surfaces, tournois, stats de service, H2H de facto via l'historique.
- **Historique** : depuis ~1968, standard de facto de la recherche tennis.
- **Fraîcheur** : fichiers Git, pas live.
- **Coût** : gratuit.
- **Licence** : **à valider** (conditions du dépôt, attribution). Décision humaine avant usage produit.
- **Rôle recommandé** : **socle historique ML tennis** (phase 9), pas le live.

### API-Tennis (API-Sports) / MatchPoint / tennis-api.com

- Live scores, rankings, tournois, parfois point-by-point.
- MatchPoint met en avant ATP depuis 1968 et un free tier.
- Qualité live et licence **non vérifiées en conditions réelles**.
- **Rôle recommandé** : **live tennis** à départager plus tard (API-Tennis pour cohérence famille API-Sports, MatchPoint si la profondeur ATP est supérieure). Pas de branchement maintenant.

Sportmonks n'est pas un spécialiste tennis à ce jour : ne pas l'assumer.

## 5. Cotes

Les cotes football d'API-Football / Sportmonks peuvent exister mais **ne sont pas le provider cotes recommandé** : couverture bookmaker, historique PIT et licence betting data sont le critère.

### The Odds API

- **Couverture** : football, NBA, tennis et d'autres sports ; ~40+ bookmakers ; ligues majeures.
- **Historique** : snapshots depuis **2020-06-06**, pas 10 min puis 5 min après 2022-09. Endpoint historical **payant**. Quota élevé (×10 par région/marché).
- **Fraîcheur** : polling REST, pas de WebSocket.
- **API** : documentation claire, `commence_time`, bookmakers, marchés `h2h` / spreads / totals. Format décimal disponible.
- **Coût** : free 500 crédits/mois ; paid dès ~30 $/mois ; historical coûte cher si on rejoue trop de timestamps.
- **Licence** : données de bookmakers, pas un flux officiel Sportradar. Relire l'usage « commercial odds display ».
- **PIT** : le `date` de snapshot est exactement ce qu'il faut pour `available_at`.
- **Limite** : ligues longues traîne et books asiatiques moins riches que certains concurrents.

**Rôle V1 validé** : **provider cotes principal** (live + historique depuis 2020). Compte et clé restent hors Git ; pas de branchement par cet ADR.

### football-data.co.uk

Complément **football closing** plus profond que 2020. À aligner via entity resolution (noms d'équipes ≠ IDs The Odds API).

### Odds-API.io

Plus de bookmakers, WebSocket, ligues longues. Moins « standard » dans l'écosystème research. Alternative si The Odds API est trop étroit. **Décision humaine.**

### Sportradar Unified Odds / OpticOdds / Unabated

Entreprise, droits, streaming. 10³ $/mois. Reporter.

### Règles cotes

- Ne jamais interpoler une cote manquante.
- Ne jamais réutiliser une cote d'un autre match.
- Préférer un bookmaker de référence documenté (ex. Pinnacle closing quand disponible) plutôt qu'une moyenne non spécifiée.
- L'overround se calcule dans le Value Engine, pas à l'ingestion.

## 6. Décisions V1 validées (2026-09-10)

Validé par le propriétaire produit. Détail : [ADR 0005](adr/0005-data-providers-v1.md).
**Aucun compte n'a été ouvert par cette validation. Aucune clé n'entre dans Git.**

| Flux | Décision | Plan / borne | Recours |
| --- | --- | --- | --- |
| Football live / stats | **Sportmonks Growth** | ~30 ligues, ~99 €/mois ; pas Starter, pas Pro | Pro si Growth insuffisant ; API-Football en filet |
| Cotes | **The Odds API** | Séparé des stats ; historical à budgéter | Odds-API.io |
| Ligues football V1 | Top 5 + C1 | PL, La Liga, Bundesliga, Serie A, Ligue 1, Champions League | Élargissement = nouvelle décision |
| Historique football produit | Backfill Sportmonks Growth sur ces ligues | Selon pack historique du plan | — |
| Historique football recherche / backtest | football-data.co.uk | **Recherche et backtest seulement** jusqu'à validation licence commerciale | The Odds API depuis 2020 |
| Basketball | Reporté (phase 8) | BALLDONTLIE | — |
| Tennis | Reporté (phase 9) | Sackmann / live à décider | — |
| Event-level football | Reporté | Pas de StatsBomb Open Data en SaaS | StatsBomb commercial plus tard |
| Raw | Filesystem en dev | S3-compatible plus tard | — |

## 7. Pourquoi ces choix

1. **Séparer stats et cotes** évite un lock-in et un trou PIT sur l'historique des prix.
2. **Sportmonks Growth plutôt que Pro** : six compétitions V1 tiennent dans ~30 ligues ; Pro reste un palier si les stats ou la C1 sont incomplètes.
3. **The Odds API** est le meilleur compromis documenté pour des snapshots horodatés multi-sports, condition du Value Finder et du backtest post-2020.
4. **football-data.co.uk** reste précieux pour 20+ ans de closing 1X2, mais **n'entre pas dans le produit** tant que la licence commerciale n'est pas explicite.
5. **BALLDONTLIE** et **Sackmann** restent le plan des phases 8 et 9.
6. **StatsBomb Open Data** est excellent pour apprendre, dangereux juridiquement dans un produit payant.

## 8. Décisions humaines encore ouvertes

1. Lecture contractuelle Sportmonks Growth : ligues exactes, historique, xG, clause usage.
2. Plan The Odds API (régions, crédits historical, politique de rejeu).
3. Licence commerciale football-data.co.uk — **bloquante** pour toute expo produit.
4. Bookmaker de référence figé (Pinnacle closing si réellement disponible).
5. Compte et région du store S3.
6. Création des comptes et injection des secrets **hors Git**, puis branchement d'un adapter à la fois.

La validation des fournisseurs **n'autorise pas** encore `PREDICTA_INGESTION_ENABLE_LIVE=true`. Le branchement est une étape séparée.
