from __future__ import annotations

from decimal import Decimal

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.grounding import assert_statements_grounded
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
from app.ai_analyst.statements import FactualClaim, GroundedStatement, render_statements
from app.odds.types import Football1x2Selection


def format_percent(value: Decimal) -> str:
    rendered = f"{(value * Decimal(100)):.1f}"
    return f"{rendered.replace('.', ',')} %"


def format_points(value: Decimal) -> str:
    rendered = f"{(value * Decimal(100)):.1f}"
    signed = rendered if value < 0 else f"+{rendered}"
    return f"{signed.replace('.', ',')} points"


def _favorite_claims(
    context: AnalystContext,
    favorite: Football1x2Selection,
    favorite_field: str,
    probability: Decimal,
) -> tuple[FactualClaim, ...]:
    claims = [
        FactualClaim("version", context.prediction.model_version, "model_version"),
        FactualClaim("probability", float(probability), favorite_field),
    ]
    if favorite is Football1x2Selection.HOME and context.identity.home_team:
        claims.append(FactualClaim("team", context.identity.home_team, "home_team"))
    elif favorite is Football1x2Selection.AWAY and context.identity.away_team:
        claims.append(FactualClaim("team", context.identity.away_team, "away_team"))
    return tuple(claims)


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
        explanation = self.assemble(context)
        assert_statements_grounded(context, self.grounded_summary(context))
        return explanation

    def assemble(self, context: AnalystContext) -> FootballAnalystExplanation:
        """Build a complete DTO from AnalystContext. Narrative grounding is separate."""

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
        statements = self.grounded_summary(context)
        return FootballAnalystExplanation(
            summary=render_statements(statements),
            key_factors=factors,
            strengths=self._strengths(context),
            risks=self._risks(context),
            confidence=confidence_from_context(context),
            data_quality=quality,
            generated_at=context.generated_at,
            analysis_version=ANALYST_VERSION,
            provider=ANALYST_PROVIDER_ID,
        )

    def grounded_summary(self, context: AnalystContext) -> tuple[GroundedStatement, ...]:
        favorite = context.favorite_selection()
        probability = context.prediction.probability(favorite)
        label = selection_label(context, favorite)
        favorite_field = {
            Football1x2Selection.HOME: "home_probability",
            Football1x2Selection.DRAW: "draw_probability",
            Football1x2Selection.AWAY: "away_probability",
        }[favorite]
        statements = [
            GroundedStatement(
                statement=(
                    f"Le modèle {context.prediction.model_version} attribue "
                    f"{format_percent(probability)} de probabilité à {label}."
                ),
                evidence_ids=(
                    "prediction.model_version",
                    f"prediction.{favorite_field}",
                    "prediction.model_favorite",
                ),
                factual_claims=_favorite_claims(context, favorite, favorite_field, probability),
            )
        ]
        if context.value is not None:
            statements.extend(
                [
                    GroundedStatement(
                        statement=(
                            "La probabilité implicite brute de la cote disponible est de "
                            f"{format_percent(context.value.implied_probability)}."
                        ),
                        evidence_ids=("value.implied_probability", "value.odds"),
                        factual_claims=(
                            FactualClaim(
                                "probability",
                                float(context.value.implied_probability),
                                "implied_probability",
                            ),
                        ),
                    ),
                    GroundedStatement(
                        statement=f"L'écart modèle-marché (edge) est de {format_points(context.value.edge)}.",
                        evidence_ids=("value.edge",),
                        factual_claims=(FactualClaim("edge", float(context.value.edge), "edge"),),
                    ),
                    GroundedStatement(
                        statement=(
                            f"L'espérance théorique (EV) calculée par {context.value.value_engine_version} "
                            f"est de {format_points(context.value.ev)}."
                        ),
                        evidence_ids=("value.ev", "value.value_engine_version"),
                        factual_claims=(
                            FactualClaim("ev", float(context.value.ev), "ev"),
                            FactualClaim("version", context.value.value_engine_version, "value_engine_version"),
                        ),
                    ),
                ]
            )
        else:
            statements.append(
                GroundedStatement(
                    statement=(
                        "Aucune cote PIT n'est disponible dans le contexte validé ; "
                        "aucune probabilité implicite, edge ou EV n'est affirmée."
                    ),
                    evidence_ids=("value.odds", "value.edge", "value.ev"),
                    factual_claims=(),
                )
            )
        statements.append(
            GroundedStatement(
                statement="Ces valeurs sont des estimations statistiques, pas un résultat futur.",
                evidence_ids=(),
                factual_claims=(),
            )
        )
        if context.missing():
            statements.append(
                GroundedStatement(
                    statement=(
                        "Données explicitement indisponibles : "
                        + ", ".join(context.missing())
                        + ". Elles n'ont pas été complétées."
                    ),
                    evidence_ids=(),
                    factual_claims=(),
                )
            )
        return tuple(statements)

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
