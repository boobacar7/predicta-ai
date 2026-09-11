from __future__ import annotations

import re
from decimal import Decimal

from app.ai_analyst.context import AnalystContext, AnalystEvidence
from app.ai_analyst.language import FORBIDDEN_CLAIMS, UNSUPPORTED_INVENTED_TOPICS
from app.ai_analyst.models import FootballAnalystExplanation
from app.ai_analyst.statements import FactualClaim, GroundedStatement
from app.odds.types import Football1x2Selection

VALUE_ONLY_FACTORS = frozenset({"market_probability", "edge", "ev", "data_freshness"})
PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")
ODDS_RE = re.compile(
    r"(?:odds|cote|priced at|price of|prix de)\s*(?:=|de|:)?\s*(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
EV_RE = re.compile(r"(?:\bev\b|espérance(?: théorique)?)\s*(?:=|de|:)?\s*([+-]?\d+(?:[.,]\d+)?)", re.IGNORECASE)
EDGE_RE = re.compile(r"\bedge\b\s*(?:=|de|:)?\s*([+-]?\d+(?:[.,]\d+)?)", re.IGNORECASE)
POINTS_RE = re.compile(r"([+-]\d+(?:[.,]\d+)?)\s*points", re.IGNORECASE)
TEAM_TOKEN_RE = re.compile(r"\bTeam\s+[A-Z0-9]+\b")
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?")
NAME_TOKEN = r"(?:St\.\s+)?[A-Z][A-Za-zÀ-ÿ']+"
PROPER_NAME_RE = re.compile(
    rf"\b({NAME_TOKEN}(?:\s+(?:d'|de |del |l'|la |le )?{NAME_TOKEN})+)\b"
)
ACRONYM_RE = re.compile(r"\b([A-Z]{2,5})\b")
TITLE_TOKEN_RE = re.compile(r"\b([A-Z][a-zÀ-ÿ]{4,})\b")
NUMBER_RE = re.compile(r"(?<![\w.-])([+-]?\d+(?:[.,]\d+)?)(?![\w.])")
MODEL_PROBABILITY_RE = re.compile(
    r"model probability|probabilit[ée]s? (?:modèle|modélisée|modeled)|highest (?:model )?probability|"
    r"plus haute probabilit[ée]|probabilit[ée] supérieure",
    re.IGNORECASE,
)
HIGHEST_PROBABILITY_RE = re.compile(
    r"highest (?:model )?probability|plus haute probabilit[ée](?: modèle)?|"
    r"la plus haute probabilit[ée]",
    re.IGNORECASE,
)
BEST_VALUE_RE = re.compile(
    r"best value|meilleure valeur|meilleure value|the value pick",
    re.IGNORECASE,
)
LIVE_AFFIRMATION_RE = re.compile(
    r"live market(?: data)?|live odds|cotes live|données live|uses live|using live|"
    r"marché live|real-time market",
    re.IGNORECASE,
)
LIVE_NEGATION_RE = re.compile(
    r"pas (?:être )?présenté(?:es)? comme live|not (?:be )?presented as live|"
    r"ne (?:doit|peuvent|peut) pas[^.]*live|not live|pas live",
    re.IGNORECASE,
)
NARRATIVE_PROPER_NAMES = frozenset({"value engine"})
STRUCTURAL_ACRONYMS = frozenset({"HOME", "AWAY", "DRAW", "EV", "PIT", "AI", "HTTP", "JSON", "DTO", "ID", "UTC"})
FUNCTION_WORDS = frozenset(
    {
        "the",
        "this",
        "that",
        "these",
        "those",
        "there",
        "their",
        "then",
        "when",
        "with",
        "from",
        "elles",
        "elle",
        "ils",
        "eux",
        "nous",
        "vous",
        "ceci",
        "cela",
        "ceux",
        "cette",
        "cet",
        "ces",
        "model",
        "value",
        "engine",
        "selection",
        "favorite",
        "issue",
        "match",
        "league",
        "probability",
        "expected",
        "analysis",
        "analyst",
        "status",
        "version",
        "candidate",
        "champion",
        "implied",
        "theoretical",
        "available",
        "complete",
        "identity",
        "payload",
        "source",
        "sources",
        "fait",
        "faits",
        "valeurs",
        "données",
        "modèle",
        "probabilité",
        "implicite",
        "espérance",
        "théorique",
        "statut",
        "disponible",
        "identit",
        "incertitude",
        "texte",
        "reste",
        "interprétatif",
        "estimations",
        "statistiques",
        "résultat",
        "futur",
        "confiance",
        "limitée",
        "métadonnées",
        "suivantes",
        "aucune",
        "cote",
        "cotes",
        "analyse",
        "équipe",
        "domicile",
        "extérieur",
        "écart",
        "combine",
        "présenté",
        "présentes",
        "contexte",
        "validé",
        "structurelle",
        "complète",
        "servi",
        "candidat",
        "production",
        "marquées",
        "stale",
        "partial",
        "explicitement",
        "indisponibles",
        "complétées",
        "attribu",
        "modélisée",
        "brute",
        "marché",
        "calculée",
        "par",
        "n'est",
    }
)


class AnalystGroundingError(ValueError):
    """Provider output referenced a fact that is not in AnalystContext."""


def assert_grounded(context: AnalystContext, explanation: FootballAnalystExplanation) -> None:
    """Refuse narrative that invents facts. Numeric DTOs stay owned by the service."""

    evidence = context.evidence()
    allowed_numbers = {
        item.value
        for item in evidence
        if item.availability == "available" and isinstance(item.value, int | float)
    }
    allowed_sources = {item.source for item in evidence if item.availability == "available"}
    for factor in explanation.key_factors:
        if factor.source not in allowed_sources:
            raise AnalystGroundingError(f"Factor source '{factor.source}' is outside AnalystContext.")
        if factor.type in VALUE_ONLY_FACTORS and context.value is None:
            raise AnalystGroundingError(f"Factor '{factor.type}' is unavailable in AnalystContext.")
        if factor.value is not None:
            grounded = any(abs(float(factor.value) - float(item)) < 1e-9 for item in allowed_numbers)
            if not grounded:
                raise AnalystGroundingError(f"Factor value {factor.value} is not present in AnalystContext.")
    texts = (
        explanation.summary,
        explanation.confidence.basis,
        *explanation.strengths,
        *explanation.risks,
    )
    for text in texts:
        _assert_text_grounded(context, text)


def assert_statements_grounded(context: AnalystContext, statements: tuple[GroundedStatement, ...]) -> None:
    """Refuse structured claims that are not present on AnalystEvidence."""

    evidence = context.evidence()
    ids = {item.evidence_id for item in evidence}
    fields = {item.source_field: item for item in evidence}
    for statement in statements:
        if any(evidence_id not in ids for evidence_id in statement.evidence_ids):
            raise AnalystGroundingError("GroundedStatement referenced an unknown evidence_id.")
        for claim in statement.factual_claims:
            _assert_claim_grounded(fields, claim)
        _assert_text_grounded(context, statement.statement)
        _assert_evidence_types_match(context, statement.statement, statement.evidence_ids, evidence)


def _assert_claim_grounded(fields: dict[str, AnalystEvidence], claim: FactualClaim) -> None:
    item = fields.get(claim.source_field)
    if item is None or item.availability != "available":
        raise AnalystGroundingError(
            f"FactualClaim {claim.kind}={claim.value} is not available in AnalystContext."
        )
    if not _values_match(item.value, claim.value):
        raise AnalystGroundingError(
            f"FactualClaim {claim.kind}={claim.value} does not match AnalystEvidence."
        )


def _assert_text_grounded(context: AnalystContext, text: str) -> None:
    forbidden = _forbidden_term(text)
    if forbidden is not None:
        raise AnalystGroundingError(f"Analyst text contains forbidden language: {forbidden}.")
    invented = _unsupported_topic(text)
    if invented is not None:
        raise AnalystGroundingError(f"Analyst text invents unsupported topic: {invented}.")
    _assert_favorite_not_confused(context, text)
    _assert_candidate_not_promoted(context, text)
    _assert_data_mode_not_contradicted(context, text)
    scanned = _mask_grounded_literals(context, text)
    allowed_percents = _allowed_percents(context)
    model_percents = _model_percents(context)
    for raw in PERCENT_RE.findall(scanned):
        value = _to_decimal(raw)
        if value not in allowed_percents:
            raise AnalystGroundingError(f"Percent claim {raw}% is not present in AnalystContext.")
        if _has_model_probability_language(scanned) and value not in model_percents:
            raise AnalystGroundingError(f"Model-probability percent {raw}% is not a model probability.")
    if context.value is None:
        if ODDS_RE.search(scanned):
            raise AnalystGroundingError("Odds were asserted while unavailable in AnalystContext.")
        lowered = scanned.casefold()
        for claim in ("edge", "espérance", "implicite brute"):
            if claim in lowered and "aucune" not in lowered and "n'est affirmée" not in lowered:
                raise AnalystGroundingError("Unavailable value facts were asserted.")
    else:
        allowed_odds = {_quantize(_to_decimal(str(context.value.odds)))}
        for raw in ODDS_RE.findall(scanned):
            if _quantize(_to_decimal(raw)) not in allowed_odds:
                raise AnalystGroundingError(f"Odds claim {raw} is not present in AnalystContext.")
        allowed_signed = _allowed_signed_metrics(context)
        for raw in (*EV_RE.findall(scanned), *EDGE_RE.findall(scanned), *POINTS_RE.findall(scanned)):
            if _quantize(_to_decimal(raw)) not in allowed_signed:
                raise AnalystGroundingError(f"Signed metric claim {raw} is not present in AnalystContext.")
    allowed_numbers = _allowed_numeric_tokens(context)
    for raw in NUMBER_RE.findall(scanned):
        if _to_decimal(raw) not in allowed_numbers:
            raise AnalystGroundingError(f"Numeric claim {raw} is not present in AnalystContext.")
    allowed_names = _allowed_names(context)
    for token in TEAM_TOKEN_RE.findall(text):
        if token.casefold() not in allowed_names:
            raise AnalystGroundingError(f"Team token '{token}' is not present in AnalystContext.")
    for name in (*PROPER_NAME_RE.findall(text), *ACRONYM_RE.findall(text), *TITLE_TOKEN_RE.findall(text)):
        if _name_allowed(name, allowed_names):
            continue
        raise AnalystGroundingError(f"Entity '{name}' is not present in AnalystContext.")
    allowed_days = _allowed_days(context)
    for raw in ISO_DATE_RE.findall(text):
        if raw[:10] not in allowed_days:
            raise AnalystGroundingError(f"Date '{raw}' is not present in AnalystContext.")


def _assert_evidence_types_match(
    context: AnalystContext,
    statement: str,
    evidence_ids: tuple[str, ...],
    evidence: tuple[AnalystEvidence, ...],
) -> None:
    if not evidence_ids:
        if _has_model_probability_language(statement) or ODDS_RE.search(statement) or EV_RE.search(statement):
            raise AnalystGroundingError("Factual claim is missing supporting evidence_ids.")
        return
    by_id = {item.evidence_id: item for item in evidence}
    cited_fields = {
        by_id[evidence_id].source_field
        for evidence_id in evidence_ids
        if evidence_id in by_id and by_id[evidence_id].availability == "available"
    }
    scanned = _mask_grounded_literals(context, statement)
    percents = {_to_decimal(raw) for raw in PERCENT_RE.findall(scanned)}
    cited_percents = _cited_percents(cited_fields, context)
    if percents and not percents.issubset(cited_percents):
        raise AnalystGroundingError("Percent claim is not supported by cited evidence.")
    if _has_model_probability_language(scanned):
        model_fields = {"home_probability", "draw_probability", "away_probability", "model_favorite"}
        if not cited_fields.intersection(model_fields):
            raise AnalystGroundingError("Model probability claim is not supported by cited evidence.")
        if percents and not percents.issubset(_model_percents(context)):
            raise AnalystGroundingError("Cited evidence cannot support the asserted model probability.")
    if BEST_VALUE_RE.search(scanned) and "value_selection" not in cited_fields:
        raise AnalystGroundingError("Value claim is not supported by cited evidence.")
    value_selection_claim = re.search(
        r"value selection|value_selection|sélection de valeur",
        scanned,
        re.IGNORECASE,
    )
    if value_selection_claim and "value_selection" not in cited_fields:
        raise AnalystGroundingError("Value selection claim is not supported by cited evidence.")
    if ODDS_RE.search(scanned) and "odds" not in cited_fields:
        raise AnalystGroundingError("Odds claim is not supported by cited evidence.")


def _cited_percents(cited_fields: set[str], context: AnalystContext) -> set[Decimal]:
    mapping = {
        "home_probability": context.prediction.home_probability,
        "draw_probability": context.prediction.draw_probability,
        "away_probability": context.prediction.away_probability,
    }
    allowed: set[Decimal] = set()
    for field, value in mapping.items():
        if field in cited_fields:
            allowed.update(_percent_forms(value))
    if context.value is None:
        return allowed
    value_fields = {
        "implied_probability": context.value.implied_probability,
        "no_vig_probability": context.value.no_vig_probability,
        "edge": abs(context.value.edge),
        "ev": abs(context.value.ev),
    }
    for field, value in value_fields.items():
        if field in cited_fields:
            allowed.update(_percent_forms(value))
    return allowed


def _unsupported_topic(text: str) -> str | None:
    lowered = text.casefold()
    for term in UNSUPPORTED_INVENTED_TOPICS:
        needle = term.casefold()
        if " " in needle:
            if needle in lowered:
                return term
            continue
        if re.search(rf"\b{re.escape(needle)}\b", lowered):
            return term
    return None


def _assert_favorite_not_confused(context: AnalystContext, text: str) -> None:
    favorite = context.favorite_selection()
    value_selection = context.value_selection
    for sentence in re.split(r"[.!?]", text):
        lowered = sentence.casefold()
        mentioned = _mentioned_selections(context, sentence)
        if HIGHEST_PROBABILITY_RE.search(sentence) and any(selection is not favorite for selection in mentioned):
            raise AnalystGroundingError("Narrative presents a non-favorite as having the highest model probability.")
        if BEST_VALUE_RE.search(sentence):
            if value_selection is None or any(selection is not value_selection for selection in mentioned):
                raise AnalystGroundingError("Narrative presents a non-value selection as the best value.")
        if value_selection is None or value_selection is favorite:
            continue
        favorite_markers = (
            "favori du modèle",
            "favorite du modèle",
            "model favorite",
            "favori modèle",
            "issue favorite",
        )
        negation = ("n'est pas", "n’est pas", "pas le favori", "not the model favorite")
        if not any(marker in lowered for marker in favorite_markers):
            continue
        if any(flag in lowered for flag in negation):
            continue
        if value_selection in mentioned and favorite not in mentioned:
            raise AnalystGroundingError("Narrative presents value_selection as the model favorite.")


def _mentioned_selections(context: AnalystContext, sentence: str) -> set[Football1x2Selection]:
    lowered = sentence.casefold()
    mentioned: set[Football1x2Selection] = set()
    home_labels = ["home", "domicile"]
    away_labels = ["away", "extérieur", "visitor", "visiteur"]
    if context.identity.home_team:
        home_labels.append(context.identity.home_team)
    if context.identity.away_team:
        away_labels.append(context.identity.away_team)
    if any(label.casefold() in lowered for label in home_labels):
        mentioned.add(Football1x2Selection.HOME)
    if any(label.casefold() in lowered for label in away_labels):
        mentioned.add(Football1x2Selection.AWAY)
    if any(label in lowered for label in ("draw", "nul", "match nul")):
        mentioned.add(Football1x2Selection.DRAW)
    return mentioned


def _assert_candidate_not_promoted(context: AnalystContext, text: str) -> None:
    if context.prediction.model_status != "candidate":
        return
    lowered = text.casefold()
    promoted = ("modèle champion", "champion model", "modèle est un champion")
    if any(term in lowered for term in promoted) and "pas un champion" not in lowered:
        raise AnalystGroundingError("Narrative promotes a candidate model to champion.")


def _assert_data_mode_not_contradicted(context: AnalystContext, text: str) -> None:
    if context.data_mode != "mock":
        return
    for sentence in re.split(r"[.!?]", text):
        if not LIVE_AFFIRMATION_RE.search(sentence):
            continue
        if LIVE_NEGATION_RE.search(sentence):
            continue
        raise AnalystGroundingError("Narrative presents mock data_mode as live.")


def _forbidden_term(text: str) -> str | None:
    lowered = text.casefold()
    for term in FORBIDDEN_CLAIMS:
        if " " in term or "%" in term:
            if term in lowered:
                return term
            continue
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            return term
    return None


def _has_model_probability_language(text: str) -> bool:
    return MODEL_PROBABILITY_RE.search(text) is not None


def _model_percents(context: AnalystContext) -> set[Decimal]:
    allowed: set[Decimal] = set()
    for value in (
        context.prediction.home_probability,
        context.prediction.draw_probability,
        context.prediction.away_probability,
    ):
        allowed.update(_percent_forms(value))
    return allowed


def _allowed_percents(context: AnalystContext) -> set[Decimal]:
    values = [
        context.prediction.home_probability,
        context.prediction.draw_probability,
        context.prediction.away_probability,
    ]
    if context.value is not None:
        values.extend([context.value.implied_probability, context.value.no_vig_probability])
        values.append(abs(context.value.edge))
        values.append(abs(context.value.ev))
    allowed: set[Decimal] = set()
    for value in values:
        allowed.update(_percent_forms(value))
    return allowed


def _percent_forms(value: Decimal) -> set[Decimal]:
    percent = (value * Decimal(100)).quantize(Decimal("0.1"))
    return {percent, abs(percent)}


def _allowed_signed_metrics(context: AnalystContext) -> set[Decimal]:
    if context.value is None:
        return set()
    allowed = set()
    for value in (context.value.edge, context.value.ev):
        points = (value * Decimal(100)).quantize(Decimal("0.1"))
        allowed.add(points)
        allowed.add(_quantize(value))
    return allowed


def _allowed_numeric_tokens(context: AnalystContext) -> set[Decimal]:
    allowed = {_to_decimal(str(value)) for value in _model_percents(context)}
    allowed.update(_to_decimal(str(value)) for value in _allowed_percents(context))
    for value in (
        context.prediction.home_probability,
        context.prediction.draw_probability,
        context.prediction.away_probability,
    ):
        allowed.add(_quantize(value))
        allowed.add(_to_decimal(str(value)))
    if context.value is not None:
        allowed.add(_quantize(context.value.odds))
        allowed.add(_to_decimal(str(context.value.odds)))
        allowed.add(_quantize(context.value.implied_probability))
        allowed.add(_quantize(context.value.no_vig_probability))
        allowed.update(_allowed_signed_metrics(context))
        age = context.odds_age_seconds()
        if age is not None:
            allowed.add(_quantize(Decimal(str(age))))
            allowed.add(Decimal(str(int(age))))
    for day in _allowed_days(context):
        allowed.add(Decimal(day[:4]))
    allowed.update({Decimal(1), Decimal(2)})
    return allowed


def _allowed_names(context: AnalystContext) -> set[str]:
    names = {
        context.identity.league.casefold(),
        context.prediction.model_version.casefold(),
        context.prediction.dataset_version.casefold(),
    }
    if context.identity.home_team:
        names.add(context.identity.home_team.casefold())
    if context.identity.away_team:
        names.add(context.identity.away_team.casefold())
    if context.value is not None:
        names.add(context.value.value_engine_version.casefold())
    return names


def _name_allowed(name: str, allowed: set[str]) -> bool:
    folded = name.casefold()
    if folded in NARRATIVE_PROPER_NAMES or folded in FUNCTION_WORDS:
        return True
    if name in STRUCTURAL_ACRONYMS:
        return True
    if name[:2] in {"L'", "D'", "N'", "C'"}:
        return True
    if folded in allowed:
        return True
    return any(re.search(rf"\b{re.escape(folded)}\b", candidate) for candidate in allowed)


def _mask_grounded_literals(context: AnalystContext, text: str) -> str:
    masked = text
    literals = [
        context.prediction.model_version,
        context.prediction.dataset_version,
        context.identity.league,
        context.identity.match_id,
        "1X2",
        "1x2",
    ]
    if context.identity.home_team:
        literals.append(context.identity.home_team)
    if context.identity.away_team:
        literals.append(context.identity.away_team)
    if context.value is not None:
        literals.append(context.value.value_engine_version)
        literals.append(context.value.odds_source)
    literals.extend(ISO_DATE_RE.findall(text))
    for literal in sorted({item for item in literals if item}, key=len, reverse=True):
        masked = re.sub(re.escape(literal), " ", masked, flags=re.IGNORECASE)
    return masked


def _allowed_days(context: AnalystContext) -> set[str]:
    return {
        context.identity.kickoff_at.date().isoformat(),
        context.prediction.cutoff_at.date().isoformat(),
    }


def _values_match(evidence: str | float | None, claim: str | float) -> bool:
    if evidence is None:
        return False
    if isinstance(evidence, int | float) or isinstance(claim, int | float):
        try:
            return abs(float(evidence) - float(claim)) < 1e-9
        except (TypeError, ValueError):
            return False
    return str(evidence).casefold() == str(claim).casefold()


def _to_decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ".").replace("+", ""))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))
