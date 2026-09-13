"""Backend-owned renderer. LLM free text never enters the DTO."""

from __future__ import annotations

from app.ai_analyst.claims import resolve_subject
from app.ai_analyst.context import AnalystContext
from app.ai_analyst.deterministic import format_percent, format_points, selection_label
from app.ai_analyst.statements import GroundedClaim, StylePayload

_TONE_LEAD = {
    "neutral": "Le contexte validé est relu avec prudence",
    "analytical": "Le contexte validé est relu de façon analytique",
    "concise": "Le contexte validé est résumé",
}
_FOCUS_TAIL = {
    "prediction": "sur la prédiction modèle",
    "value": "sur la value théorique",
    "data_quality": "sur la qualité des données",
}


def render_analyst_summary(
    context: AnalystContext,
    claims: tuple[GroundedClaim, ...],
    style: StylePayload,
) -> str:
    """Build the published summary from validated claims and AnalystContext only.

    Style enums may change phrasing of the non-factual opener. They cannot
    inject numbers, teams, or other facts. LLM narrative is not a parameter.
    """

    opener = _style_opener(style)
    rendered = [sentence for claim in claims if (sentence := _render_claim(context, claim))]
    return " ".join(part for part in (opener, *rendered) if part)


def _style_opener(style: StylePayload) -> str:
    lead = _TONE_LEAD[style.tone]
    focus = _FOCUS_TAIL[style.focus]
    sentence = f"{lead} {focus}."
    if style.verbosity == "medium":
        return f"{sentence} Les faits publiés restent limités aux claims validées."
    return sentence


def _render_claim(context: AnalystContext, claim: GroundedClaim) -> str:
    if claim.claim_type == "model_probability":
        selection = resolve_subject(context, claim.subject)
        if selection is None:
            return ""
        return (
            f"Le modèle estime {format_percent(context.prediction.probability(selection))} "
            f"de probabilité à {selection_label(context, selection)}."
        )
    if claim.claim_type == "probability_comparison":
        return "La comparaison de probabilités modèle est cohérente avec le contexte validé."
    if claim.claim_type == "model_favorite":
        favorite = context.favorite_selection()
        return f"Le favori du modèle est {favorite.value} ({selection_label(context, favorite)})."
    if claim.claim_type == "value_selection" and context.value_selection is not None:
        pick = context.value_selection
        return f"La sélection de valeur est {pick.value} ({selection_label(context, pick)})."
    if claim.claim_type == "odds" and context.value is not None:
        return f"La cote PIT disponible est {context.value.odds}."
    if claim.claim_type == "implied_probability" and context.value is not None:
        return (
            "La probabilité implicite brute de la cote disponible est de "
            f"{format_percent(context.value.implied_probability)}."
        )
    if claim.claim_type == "ev" and context.value is not None:
        return f"L'espérance théorique (EV) est de {format_points(context.value.ev)}."
    if claim.claim_type == "edge" and context.value is not None:
        return f"L'écart modèle-marché (edge) est de {format_points(context.value.edge)}."
    if claim.claim_type == "data_mode":
        return f"Ces faits sont servis en data_mode {context.data_mode} et ne doivent pas être présentés comme live."
    if claim.claim_type == "model_status":
        return (
            f"Le modèle {context.prediction.model_version} a le statut {context.prediction.model_status}, "
            "pas un statut de production promu."
        )
    if claim.claim_type == "team":
        selection = resolve_subject(context, claim.subject if claim.subject is not None else str(claim.value or ""))
        if selection is None:
            return ""
        return f"L'équipe concernée est {selection_label(context, selection)}."
    if claim.claim_type == "league":
        return f"La compétition concernée est {context.identity.league}."
    return ""
