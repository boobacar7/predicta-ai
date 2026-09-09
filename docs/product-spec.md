# Spécification produit

## 1. Positionnement

PREDICTA AI est une plateforme SaaS d'analyse sportive assistée par IA. Elle aide un utilisateur à comprendre un événement, les probabilités estimées par les modèles, les facteurs qui les influencent et la performance historique du système.

Le produit n'accepte pas de mises et ne se présente pas comme un bookmaker. Il ne promet aucun résultat ni rendement financier.

## 2. Utilisateurs et besoins

### Amateur éclairé

- consulter rapidement les matchs du jour;
- comprendre une probabilité sans maîtriser tous les modèles;
- distinguer confiance du modèle et certitude sportive.

### Analyste sportif

- explorer les statistiques, facteurs et comparaisons;
- connaître la fraîcheur, la source et la complétude des données;
- vérifier la cohérence historique d'un signal.

### Utilisateur orienté value

- comparer probabilité calibrée et probabilité implicite;
- comprendre l'overround, l'edge et l'EV;
- suivre les mouvements de cotes sans promesse de gain.

## 3. Sports et ordre de livraison

1. Football : premier périmètre data et ML.
2. Basketball : extension après stabilisation du pipeline football.
3. Tennis : extension avec Elo spécifique à la surface et statistiques individuelles.

Les contrats utilisent des concepts communs et des extensions propres à chaque sport. Ils ne forcent pas un schéma universel artificiel pour les statistiques.

## 4. Capacités cibles

- Dashboard et matchs du jour.
- Calendrier et filtres par sport, date et compétition.
- Détail d'un match et statistiques disponibles.
- Probabilités calibrées, niveau de confiance et principaux facteurs.
- AI Picks fondés sur des prédictions versionnées.
- Value Finder fondé sur des cotes horodatées.
- Performance, calibration et historique des modèles.
- Analyses d'équipes, joueurs et ligues.
- AI Analyst utilisant uniquement des faits validés.
- À terme : compte, favoris, tracker, notifications et abonnements.

## 5. Navigation cible

Dashboard, Matches, AI Picks, Value Finder, Analytics, Performance, Leagues, Teams, Players, AI Analyst et Profile.

La présence dans la navigation ne signifie pas qu'une fonction est livrée. Les fonctions non disponibles doivent être masquées ou signalées comme futures, sans écran cassé.

## 6. Vocabulaire produit

- **Probabilité modèle** : estimation numérique produite par une version de modèle.
- **Probabilité calibrée** : probabilité corrigée à partir d'observations hors entraînement.
- **Confiance** : signal synthétique lié à la qualité et la stabilité des données/modèles; ce n'est pas une certitude.
- **Cote** : snapshot horodaté provenant d'une source identifiée.
- **Probabilité implicite brute** : `1 / cote décimale`.
- **Probabilité no-vig** : probabilité implicite normalisée après retrait estimé de la marge.
- **Edge** : probabilité modèle calibrée moins probabilité implicite retenue.
- **EV** : `(probabilité calibrée × cote décimale) - 1`.
- **Pick** : signal répondant à des critères documentés; jamais une garantie.
- **Donnée indisponible** : valeur absente ou inutilisable, distincte de zéro.

## 7. Règles d'intégrité

Le produit ne doit jamais inventer ou extrapoler silencieusement :

- cotes et mouvements de cotes;
- statistiques, résultats, classements et forme;
- blessures, suspensions, compositions ou disponibilité;
- identité d'une équipe, d'un joueur, d'une compétition ou d'un provider;
- performance historique d'un modèle.

Chaque donnée exposée doit pouvoir porter :

- sa source ou son origine;
- son horodatage d'observation;
- son état de fraîcheur;
- son niveau de disponibilité;
- si nécessaire, une note de qualité.

Une estimation dérivée doit être nommée comme telle et documenter ses entrées.

## 8. Règles relatives aux prédictions

À afficher :

- « Probabilité du modèle : 68 % »
- « Confiance du modèle : élevée »
- « Edge estimé : +7,2 points »
- « Données de composition indisponibles »

À proscrire :

- « garanti », « sûr », « certain », « 100 % »;
- toute promesse de rendement;
- une explication LLM présentant une hypothèse comme un fait;
- une probabilité sans version de modèle ni cutoff de données.

Les probabilités d'un marché mutuellement exclusif doivent être validées et leur somme doit respecter la tolérance documentée.

## 9. AI Analyst

L'AI Analyst reçoit un paquet de faits construit par le backend :

- contexte du match;
- statistiques autorisées avec source et timestamp;
- probabilités calibrées et version de modèle;
- facteurs explicatifs calculés;
- données explicitement indisponibles.

Il peut synthétiser, comparer et répondre. Il ne peut pas modifier les probabilités, créer des cotes, combler un champ absent ni affirmer un résultat futur. Sa réponse conserve les références aux faits utilisés.

## 10. États obligatoires de l'interface

Toute vue data-driven prévoit :

- **loading** : squelette stable, sans faux chiffres;
- **error** : message actionnable et nouvelle tentative lorsque pertinente;
- **empty** : absence réelle de résultats, distincte d'une erreur;
- **partial** : contenu disponible accompagné des lacunes;
- **stale** : contenu conservé mais fraîcheur visible;
- **responsive** : desktop, laptop, tablette et mobile;
- **accessible** : clavier, focus, contraste, libellés et alternatives aux graphiques.

## 11. Prototype frontend

Le prototype utilise des fixtures réalistes, mais fictives et marquées `mock`. Les fixtures vivent dans une couche dédiée, jamais dans les composants React.

Les composants consomment les mêmes types et services que l'API future. Le changement de `mock` vers `http` se fait par configuration et par endpoint, sans refonte visuelle.

## 12. Hors périmètre de la fondation

- frontend ou backend fonctionnel complet;
- intégration d'un provider sportif;
- schéma PostgreSQL physique et migrations;
- entraînement ou déploiement d'un modèle;
- calcul de recommandations réelles;
- authentification, paiement et notifications;
- choix définitif d'un fournisseur cloud ou LLM.

## 13. Critères d'acceptation produit

- Le positionnement « intelligence sportive, non bookmaker » est explicite.
- Toute prédiction est une probabilité traçable.
- Les données manquantes sont visibles et ne deviennent jamais `0`.
- Le Value Engine expose ses formules et entrées.
- L'AI Analyst ne reçoit que des faits structurés.
- Le frontend peut fonctionner avec mocks puis API réelle derrière le même contrat.
- Les performances sont évaluées au-delà de l'accuracy.
