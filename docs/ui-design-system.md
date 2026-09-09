# Design system PREDICTA AI

Prototype UI phase 1. Tokens, composants et règles d'usage pour rester premium, lisible et distinct d'un bookmaker.

## Positionnement visuel

Références : Linear, Stripe Dashboard, consoles fintech sombres. Contre-exemples : sites de paris, casinos, tableaux Excel, dashboards admin génériques.

Principes :

- hiérarchie typographique nette;
- beaucoup d'air;
- bordures discrètes;
- un seul accent IA (violet);
- le vert signale un écart de modèle, jamais un « bon pari »;
- le rouge est rare (live, erreur, risque).

## Tokens

| Rôle | Valeur |
| --- | --- |
| Fond | `#07090D` |
| Surface / carte | `#0E1219` |
| Surface élevée | `#151B25` |
| Texte | `#F5F7FA` |
| Texte secondaire | `#8992A3` |
| Accent IA | `#7C6CF6` |
| Value | `#3DDC97` |
| Attention | `#F0A14A` |
| Risque | `#E36B5B` |
| Home / Draw / Away | violet / gris / bleu |

Typographie : Geist Sans pour l'UI, Geist Mono + `tabular-nums` pour probabilités, cotes et métriques.

Rayon : 10px (contrôles), 16px (cartes), 22px (calendrier). Ombres très discrètes.

## Motion

Transitions courtes (≈ 280 ms), easing `[0.22, 1, 0.36, 1]`. `prefers-reduced-motion` coupe animations et transitions.

## Composants domain

| Composant | Rôle |
| --- | --- |
| `MatchCard` | Brief de match, pas un coupon |
| `ProbabilityBar` | Marché calibré avec résumé accessible |
| `AIConfidence` | Qualité modèle/données, jamais une certitude |
| `ValueBadge` | Edge / EV + état stale |
| `OddsDisplay` | Snapshot horodaté, source visible |
| `DataFreshness` / `Unavailable` | Fraîcheur et absences, jamais `0` silencieux |
| `PredictionCard` | Pick versionné + critère |
| `InsightCard` | Note d'analyste |
| `PerformanceChart` | Log loss, Brier, calibration + texte SR |
| `TeamComparison` / `MatchTimeline` | Stats et événements disponibles |
| `SportFilter` / `LeagueFilter` / `CalendarStrip` | Navigation de catalogue |

## Copy

À utiliser : « Probabilité du modèle », « Confiance du modèle », « Edge estimé », « Donnée indisponible ».

À proscrire : garanti, sûr, certain, 100 %, safe bet, CTA de mise.

## Responsive

- Desktop : sidebar 256px + canvas.
- Tablette : sidebar overlay.
- Mobile : barre inférieure (Dashboard, Matchs, Picks, Value, Analyst) + menu complet.

## Accessibilité

- Skip link, landmarks, `aria-current`.
- Focus violet visible.
- Couleur non exclusive (libellés + badges).
- Graphiques avec résumé `sr-only`.
- Contraste texte secondaire contrôlé sur fond `#07090D`.

## États

Toute vue data-driven gère loading, error + retry, empty, partial et stale. Le sélecteur « Scénario mock » permet de les inspecter sans backend.
