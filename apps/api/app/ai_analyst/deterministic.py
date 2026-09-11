from __future__ import annotations

from decimal import Decimal

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.models import (
    ANALYST_PROVIDER_ID,
    ANALYST_VERSION,
    CONFIDENCE_RULE,
    FootballAnalystConfidence,
    FootballAnalystDataQuality,
    FootballAnalystExplanation,
    FootballAnalystFactor,
    selection_direction,
)
from app.odds.types import Football1x2Selection

FORBIDDEN_CLAIMS = (
    "garanti",
    "guarantee",
    "sûr",
    "sure win",
    "safe bet",
    "certain",
    "100%",
    "blessure",
    "injury",
    "composition",
    "lineup",
    "mise",
    "pari recommandé",
    "gain",
)


def format_percent(value: Decimal) -> str:
    rendered = f"{(value * Decimal(100)):.1f}"
    return f"{rendered.replace('.', ',')} %"


def format_points(value: Decimal) -> str:
    rendered = f"{(value * Decimal(100)):.1f}"
    signed = rendered if value < 0 else f"+{rendered}"
    return f"{signed.replace('.', ',')} points"


def selection_label(context: AnalystContext, selection: Football1x2Selection) -> str:
    if selection is Football1x2Selection.HOME:
        return context.identity.home_team or "l'équipe à domicile"
    if selection is Football1x2Selection.AWAY:
        return context.identity.away_team or "l'équipe à l'extérieur"
    return "le match nul"


def confidence_from_context(context: AnalystContext) -> FootballAnalystConfidence:
    complete = context.identity_complete()
    value_available = context.value is not None
    champion = context.prediction.model_status == "champion"
    live = context.data_mode == "live"
    if champion and live and complete and value_available:
        level: str = "high"
        basis = "Modèle champion, données live, identité complète et value disponible."
    elif context.prediction.model_status == "candidate" and complete and value_available:
        level = "medium"
        basis = "Modèle candidat avec identité complète et value disponible. Ce n'est pas une certitude."
    else:
        level = "low"
        gaps = list(context.missing())
        if context.prediction.model_status == "candidate":
            gaps.insert(0, "model_status=candidate")
        if context.data_mode == "mock":
            gaps.append("data_mode=mock")
        basis = "Confiance limitée par les métadonnées suivantes : " + ", ".join(gaps) + "."
    return FootballAnalystConfidence(level=level, basis=basis, rule=CONFIDENCE_RULE)


class DeterministicAnalystProvider:
    """Pure function of AnalystContext. No clock, no I/O, no randomness."""

    def generate_analysis(self, context: AnalystContext) -> FootballAnalystExplanation:
        favorite = context.favorite_selection()
        factors = self._factors(context, favorite)
        quality = FootballAnalystDataQuality(
            data_mode=context.data_mode,
            model_status=context.prediction.model_status,
            cutoff_at=context.prediction.cutoff_at,
            freshness=context.freshness(),
            availability=context.context_availability(),
            missing=list(context.missing()),
        )
        explanation = FootballAnalystExplanation(
            summary=self._summary(context, favorite),
            key_factors=factors,
            strengths=self._strengths(context),
            risks=self._risks(context),
            confidence=confidence_from_context(context),
            data_quality=quality,
            generated_at=context.generated_at,
            analysis_version=ANALYST_VERSION,
            provider=ANALYST_PROVIDER_ID,
        )
        self._assert_no_forbidden_language(explanation.summary)
        return explanation

    def _summary(self, context: AnalystContext, favorite: Football1x2Selection) -> str:
        probability = context.prediction.probability(favorite)
        sentences = [
            (
                f"Le modèle {context.prediction.model_version} attribue "
                f"{format_percent(probability)} de probabilité à {selection_label(context, favorite)}."
            )
        ]
        if context.value is not None:
            sentences.append(
                "La probabilité implicite brute de la cote disponible est de "
                f"{format_percent(context.value.implied_probability)}."
            )
            sentences.append(
                f"L'écart modèle-marché (edge) est de {format_points(context.value.edge)}."
            )
            sentences.append(
                f"L'espérance théorique (EV) calculée par {context.value.value_engine_version} "
                f"est de {format_points(context.value.ev)}."
            )
        else:
            sentences.append(
                "Aucune cote PIT n'est disponible dans le contexte validé ; "
                "aucune probabilité implicite, edge ou EV n'est affirmée."
            )
        sentences.append("Ces valeurs sont des estimations statistiques, pas un résultat futur.")
        if context.missing():
            sentences.append(
                "Données explicitement indisponibles : "
                + ", ".join(context.missing())
                + ". Elles n'ont pas été complétées."
            )
        return " ".join(sentences)

    def _factors(self, context: AnalystContext, favorite: Football1x2Selection) -> list[FootballAnalystFactor]:
        factors = [
            FootballAnalystFactor(
                type="model_probability",
                label=f"Probabilité modèle · {favorite.value}",
                value=float(context.prediction.probability(favorite)),
                direction=selection_direction(favorite),
                source=context.prediction.source,
            ),
            FootballAnalystFactor(
                type="model_status",
                label="Statut du modèle",
                value=None,
                direction="neutral",
                source=context.prediction.source,
            ),
        ]
        if context.value is not None:
            factors.extend(
                [
                    FootballAnalystFactor(
                        type="market_probability",
                        label="Probabilité implicite brute",
                        value=float(context.value.implied_probability),
                        direction=selection_direction(context.value.selection),
                        source=context.value.source,
                    ),
                    FootballAnalystFactor(
                        type="edge",
                        label="Edge modèle-marché",
                        value=float(context.value.edge),
                        direction=selection_direction(context.value.selection),
                        source=context.value.source,
                    ),
                    FootballAnalystFactor(
                        type="ev",
                        label="EV théorique",
                        value=float(context.value.ev),
                        direction=selection_direction(context.value.selection),
                        source=context.value.source,
                    ),
                    FootballAnalystFactor(
                        type="data_freshness",
                        label="Âge des cotes au cutoff (secondes)",
                        value=context.odds_age_seconds(),
                        direction="neutral",
                        source=context.value.odds_source,
                    ),
                ]
            )
        return factors

    @staticmethod
    def _strengths(context: AnalystContext) -> list[str]:
        items = ["Les trois probabilités 1X2 du modèle sont présentes dans le contexte validé."]
        if context.value is not None:
            items.append(
                f"Une analyse {context.value.value_engine_version} est disponible pour "
                f"{context.value.selection.value}."
            )
        if context.identity_complete():
            items.append("L'identité structurelle du match est complète.")
        return items

    @staticmethod
    def _risks(context: AnalystContext) -> list[str]:
        items: list[str] = []
        if context.prediction.model_status == "candidate":
            items.append("Le modèle servi est un candidat, pas un champion de production.")
        if context.data_mode == "mock":
            items.append("Le payload combine des sources mock et ne doit pas être présenté comme live.")
        if context.value is None:
            items.append("Aucune cote PIT n'est disponible ; l'analyse de value est absente.")
        elif context.freshness() == "stale":
            items.append("Les cotes disponibles au cutoff sont marquées stale.")
        if not context.identity_complete():
            items.append("L'identité d'équipe est partielle ; aucun nom manquant n'a été inventé.")
        return items

    @staticmethod
    def _assert_no_forbidden_language(summary: str) -> None:
        lowered = summary.casefold()
        for term in FORBIDDEN_CLAIMS:
            if term in lowered:
                raise ValueError(f"Analyst summary contains forbidden language: {term}.")
