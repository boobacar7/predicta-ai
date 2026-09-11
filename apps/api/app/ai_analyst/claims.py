from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.ai_analyst.context import AnalystContext, AnalystEvidence
from app.ai_analyst.language import FORBIDDEN_CLAIMS, UNSUPPORTED_INVENTED_TOPICS, first_blocked_term
from app.ai_analyst.statements import ClaimRelation, ClaimType, GroundedClaim, GroundedNarrative
from app.odds.types import Football1x2Selection

UNSUPPORTED_CLAIM_TYPES: frozenset[ClaimType] = frozenset(
    {"statistic", "injury", "lineup", "result", "event", "ranking", "recommendation"}
)
CLAIM_EVIDENCE_TYPES: dict[ClaimType, frozenset[str]] = {
    "team": frozenset({"team"}),
    "league": frozenset({"league"}),
    "kickoff": frozenset({"kickoff"}),
    "model_probability": frozenset({"model_probability"}),
    "probability_comparison": frozenset({"model_probability"}),
    "model_favorite": frozenset({"model_favorite", "model_probability"}),
    "odds": frozenset({"odds"}),
    "implied_probability": frozenset({"implied_probability"}),
    "no_vig_probability": frozenset({"no_vig_probability"}),
    "edge": frozenset({"edge"}),
    "ev": frozenset({"ev"}),
    "value_selection": frozenset({"value_selection"}),
    "value_comparison": frozenset({"ev", "edge", "value_selection"}),
    "data_mode": frozenset({"data_mode"}),
    "model_status": frozenset({"model_status"}),
}
SUBJECT_PROBABILITY_FIELD = {
    Football1x2Selection.HOME: "home_probability",
    Football1x2Selection.DRAW: "draw_probability",
    Football1x2Selection.AWAY: "away_probability",
}
STRUCTURAL_LABELS = frozenset({"home", "away", "draw"})
DIGIT_RE = re.compile(r"\d")


class ClaimGroundingError(ValueError):
    """A structured claim is incompatible with AnalystContext / AnalystEvidence."""


class EvidenceValidator:
    """evidence_id existence, availability, and claim_type ↔ evidence.type compatibility."""

    def cited(self, claim: GroundedClaim, catalog: dict[str, AnalystEvidence]) -> list[AnalystEvidence]:
        return _cited_evidence(claim, catalog)

    def assert_compatible(self, claim: GroundedClaim, cited: list[AnalystEvidence]) -> None:
        _assert_evidence_type(claim, cited)


class ClaimValidator:
    """Compares structured claims to AnalystContext. Narrative prose is not evidence."""

    def __init__(self, evidence_validator: EvidenceValidator | None = None) -> None:
        self._evidence = evidence_validator or EvidenceValidator()

    def validate(self, context: AnalystContext, claims: tuple[GroundedClaim, ...]) -> tuple[GroundedClaim, ...]:
        catalog = {item.evidence_id: item for item in context.evidence()}
        validated: list[GroundedClaim] = []
        for claim in claims:
            cited = self._evidence.cited(claim, catalog)
            self._evidence.assert_compatible(claim, cited)
            _validate_claim(context, claim, catalog)
            validated.append(claim)
        return tuple(validated)


def validate_narrative_and_claims(context: AnalystContext, narrative: GroundedNarrative) -> tuple[GroundedClaim, ...]:
    """Backend-owned validation. Prose is never a source of truth."""

    _assert_narrative_is_style(context, narrative.narrative)
    if not narrative.narrative.strip() and not narrative.claims:
        raise ClaimGroundingError("LLM narrator returned neither style narrative nor claims.")
    return validate_claims(context, narrative.claims)


def validate_claims(context: AnalystContext, claims: tuple[GroundedClaim, ...]) -> tuple[GroundedClaim, ...]:
    return ClaimValidator().validate(context, claims)


def render_grounded_narrative(context: AnalystContext, narrative: GroundedNarrative) -> str:
    rendered_claims = [sentence for claim in narrative.claims if (sentence := _render_claim(context, claim))]
    parts = [narrative.narrative.strip(), *rendered_claims]
    return " ".join(part for part in parts if part)


def resolve_subject(context: AnalystContext, subject: str | None) -> Football1x2Selection | None:
    if subject is None or str(subject).strip() == "":
        return None
    raw = str(subject).strip()
    upper = raw.upper()
    if upper in {"HOME", "AWAY", "DRAW"}:
        return Football1x2Selection(upper)
    home = context.identity.home_team
    away = context.identity.away_team
    if home and raw.casefold() == home.casefold():
        return Football1x2Selection.HOME
    if away and raw.casefold() == away.casefold():
        return Football1x2Selection.AWAY
    raise ClaimGroundingError(f"Subject '{subject}' is not present in AnalystContext.")


def _assert_narrative_is_style(context: AnalystContext, text: str) -> None:
    if not text.strip():
        return
    if DIGIT_RE.search(text):
        raise ClaimGroundingError("Narrative prose contained a numeric fact; numbers belong in claims.")
    lowered = text.casefold()
    for label in STRUCTURAL_LABELS:
        if re.search(rf"\b{label}\b", lowered):
            raise ClaimGroundingError(
                f"Narrative prose named selection '{label}'; factual selections belong in claims."
            )
    for name in (context.identity.home_team, context.identity.away_team, context.identity.league):
        if name and name.casefold() in lowered:
            raise ClaimGroundingError("Narrative prose named a context identity; identities belong in claims.")
    blocked = first_blocked_term(text, FORBIDDEN_CLAIMS) or first_blocked_term(text, UNSUPPORTED_INVENTED_TOPICS)
    if blocked:
        raise ClaimGroundingError(f"Narrative prose asserted unsupported topic '{blocked}' without a claim.")


def _validate_claim(
    context: AnalystContext,
    claim: GroundedClaim,
    evidence: dict[str, AnalystEvidence],
) -> None:
    if claim.claim_type in UNSUPPORTED_CLAIM_TYPES:
        raise ClaimGroundingError(f"Unsupported claim type '{claim.claim_type}' has no AnalystEvidence.")
    cited = _cited_evidence(claim, evidence)
    _assert_evidence_type(claim, cited)
    if claim.claim_type == "model_probability":
        _validate_model_probability(context, claim, cited)
        return
    if claim.claim_type == "probability_comparison":
        _validate_probability_comparison(context, claim, cited)
        return
    if claim.claim_type == "model_favorite":
        _validate_model_favorite(context, claim)
        return
    if claim.claim_type == "value_selection":
        _validate_value_selection(context, claim)
        return
    if claim.claim_type == "value_comparison":
        _validate_value_comparison(context, claim, cited)
        return
    if claim.claim_type in {"ev", "edge"}:
        _validate_signed_metric(context, claim)
        return
    if claim.claim_type == "odds":
        _validate_odds(context, claim)
        return
    if claim.claim_type in {"implied_probability", "no_vig_probability"}:
        _validate_market_probability(context, claim)
        return
    if claim.claim_type == "data_mode":
        _validate_data_mode(context, claim)
        return
    if claim.claim_type == "model_status":
        if str(claim.value).casefold() != context.prediction.model_status.casefold():
            raise ClaimGroundingError("model_status claim does not match AnalystContext.")
        return
    if claim.claim_type == "team":
        resolve_subject(context, str(claim.subject or claim.value))
        return
    if claim.claim_type == "league":
        if str(claim.value or claim.subject).casefold() != context.identity.league.casefold():
            raise ClaimGroundingError("league claim is not present in AnalystContext.")
        return
    if claim.claim_type == "kickoff":
        expected = context.identity.kickoff_at.isoformat()
        if str(claim.value) not in {expected, expected.replace("+00:00", "Z")}:
            raise ClaimGroundingError("kickoff claim is not present in AnalystContext.")
        return
    raise ClaimGroundingError(f"Unsupported claim type '{claim.claim_type}'.")


def _cited_evidence(claim: GroundedClaim, evidence: dict[str, AnalystEvidence]) -> list[AnalystEvidence]:
    if not claim.evidence_ids:
        raise ClaimGroundingError(f"Claim '{claim.claim_type}' is missing evidence_ids.")
    cited: list[AnalystEvidence] = []
    for evidence_id in claim.evidence_ids:
        item = evidence.get(evidence_id)
        if item is None:
            raise ClaimGroundingError(f"GroundedClaim referenced an unknown evidence_id: {evidence_id}.")
        if item.availability != "available":
            raise ClaimGroundingError(f"Claim '{claim.claim_type}' cited unavailable evidence '{evidence_id}'.")
        cited.append(item)
    return cited


def _assert_evidence_type(claim: GroundedClaim, cited: list[AnalystEvidence]) -> None:
    allowed = CLAIM_EVIDENCE_TYPES.get(claim.claim_type, frozenset())
    types = {item.evidence_type for item in cited}
    if allowed and not types.intersection(allowed):
        raise ClaimGroundingError(
            f"Claim '{claim.claim_type}' is not compatible with cited evidence types {sorted(types)}."
        )


def _validate_model_probability(
    context: AnalystContext,
    claim: GroundedClaim,
    cited: list[AnalystEvidence],
) -> None:
    selection = resolve_subject(context, claim.subject)
    if selection is None:
        raise ClaimGroundingError("model_probability claim is missing a subject.")
    required = SUBJECT_PROBABILITY_FIELD[selection]
    if required not in {item.source_field for item in cited}:
        raise ClaimGroundingError("model_probability claim did not cite the subject's prediction evidence.")
    if claim.value is None:
        raise ClaimGroundingError("model_probability claim is missing a value.")
    actual = context.prediction.probability(selection)
    if not _probability_matches(claim.value, actual):
        raise ClaimGroundingError(
            f"model_probability value {claim.value} is incompatible with AnalystEvidence."
        )


def _validate_probability_comparison(
    context: AnalystContext,
    claim: GroundedClaim,
    cited: list[AnalystEvidence],
) -> None:
    left = resolve_subject(context, claim.subject)
    if left is None or claim.relation is None or claim.compare_to is None:
        raise ClaimGroundingError("probability_comparison claim is missing subject, relation or compare_to.")
    left_value = context.prediction.probability(left)
    right_subject = _maybe_subject(context, claim.compare_to)
    if right_subject is not None:
        right_value = context.prediction.probability(right_subject)
        needed = {SUBJECT_PROBABILITY_FIELD[left], SUBJECT_PROBABILITY_FIELD[right_subject]}
    else:
        right_value = _as_probability(claim.compare_to)
        needed = {SUBJECT_PROBABILITY_FIELD[left]}
    cited_fields = {item.source_field for item in cited}
    if not needed.issubset(cited_fields):
        raise ClaimGroundingError("probability_comparison claim did not cite the compared prediction evidence.")
    if not _relation_holds(left_value, claim.relation, right_value):
        raise ClaimGroundingError("probability_comparison is false against AnalystContext.")


def _validate_model_favorite(context: AnalystContext, claim: GroundedClaim) -> None:
    selection = resolve_subject(context, _claim_subject(claim))
    if selection is None:
        raise ClaimGroundingError("model_favorite claim is missing a subject.")
    if selection is not context.favorite_selection():
        raise ClaimGroundingError("model_favorite claim does not match AnalystContext.")


def _validate_value_selection(context: AnalystContext, claim: GroundedClaim) -> None:
    if context.value_selection is None:
        raise ClaimGroundingError("value_selection claim is unavailable in AnalystContext.")
    selection = resolve_subject(context, _claim_subject(claim))
    if selection is None:
        raise ClaimGroundingError("value_selection claim is missing a subject.")
    if selection is not context.value_selection:
        raise ClaimGroundingError("value_selection claim does not match AnalystContext.")


def _validate_value_comparison(
    context: AnalystContext,
    claim: GroundedClaim,
    cited: list[AnalystEvidence],
) -> None:
    if context.value is None:
        raise ClaimGroundingError("value_comparison claim is unavailable in AnalystContext.")
    left = resolve_subject(context, claim.subject)
    if left is None:
        raise ClaimGroundingError("value_comparison claim is missing a subject.")
    owner = context.value.selection
    if left is not owner:
        raise ClaimGroundingError("value_comparison claim is attributed to the wrong selection.")
    del cited
    if claim.relation is None:
        raise ClaimGroundingError("value_comparison claim is missing a relation.")
    actual = context.value.ev
    if claim.compare_to is None:
        raise ClaimGroundingError("value_comparison claim is missing compare_to.")
    right_subject = _maybe_subject(context, claim.compare_to)
    if right_subject is not None:
        raise ClaimGroundingError("EV/edge for another selection is not present in AnalystContext.")
    if not _relation_holds(actual, claim.relation, _as_signed(claim.compare_to)):
        raise ClaimGroundingError("value_comparison is false against AnalystContext.")


def _validate_signed_metric(context: AnalystContext, claim: GroundedClaim) -> None:
    if context.value is None:
        raise ClaimGroundingError(f"{claim.claim_type} claim is unavailable in AnalystContext.")
    owner = context.value.selection
    selection = resolve_subject(context, claim.subject)
    if selection is not None and selection is not owner:
        raise ClaimGroundingError(f"{claim.claim_type} claim is attributed to the wrong selection.")
    actual = context.value.ev if claim.claim_type == "ev" else context.value.edge
    if claim.relation is not None:
        target = Decimal("0") if claim.compare_to is None else _as_signed(claim.compare_to)
        if not _relation_holds(actual, claim.relation, target):
            raise ClaimGroundingError(f"{claim.claim_type} relation is false against AnalystContext.")
        return
    if isinstance(claim.value, str) and claim.value.casefold() in {"high", "positive"}:
        if actual <= 0:
            raise ClaimGroundingError(f"{claim.claim_type} is not high in AnalystContext.")
        return
    if isinstance(claim.value, str) and claim.value.casefold() in {"low", "negative"}:
        if actual >= 0:
            raise ClaimGroundingError(f"{claim.claim_type} is not low in AnalystContext.")
        return
    if claim.value is None:
        return
    if not _signed_matches(claim.value, actual):
        raise ClaimGroundingError(f"{claim.claim_type} value {claim.value} is incompatible with AnalystEvidence.")


def _validate_odds(context: AnalystContext, claim: GroundedClaim) -> None:
    if context.value is None:
        raise ClaimGroundingError("odds claim is unavailable in AnalystContext.")
    selection = resolve_subject(context, claim.subject)
    if selection is not None and selection is not context.value.selection:
        raise ClaimGroundingError("odds claim is attributed to the wrong selection.")
    if claim.value is None:
        return
    actual = context.value.odds.quantize(Decimal("0.001"))
    claimed = Decimal(str(claim.value)).quantize(Decimal("0.001"))
    if claimed != actual:
        raise ClaimGroundingError(f"odds value {claim.value} is incompatible with AnalystEvidence.")


def _validate_market_probability(context: AnalystContext, claim: GroundedClaim) -> None:
    if context.value is None:
        raise ClaimGroundingError(f"{claim.claim_type} claim is unavailable in AnalystContext.")
    selection = resolve_subject(context, claim.subject)
    if selection is not None and selection is not context.value.selection:
        raise ClaimGroundingError(f"{claim.claim_type} claim is attributed to the wrong selection.")
    actual = (
        context.value.implied_probability
        if claim.claim_type == "implied_probability"
        else context.value.no_vig_probability
    )
    if claim.value is None:
        return
    if not _probability_matches(claim.value, actual):
        raise ClaimGroundingError(f"{claim.claim_type} value is incompatible with AnalystEvidence.")


def _validate_data_mode(context: AnalystContext, claim: GroundedClaim) -> None:
    raw = str(claim.value if claim.value is not None else claim.subject or "").casefold()
    if raw in {"live", "live_market", "true"}:
        raw = "live"
    if raw != context.data_mode:
        raise ClaimGroundingError("data_mode claim does not match AnalystContext.")


def _maybe_subject(context: AnalystContext, value: str | float) -> Football1x2Selection | None:
    if isinstance(value, int | float) or _looks_numeric(value):
        return None
    try:
        return resolve_subject(context, str(value))
    except ClaimGroundingError:
        return None


def _probability_matches(claimed: str | float | bool, actual: Decimal) -> bool:
    try:
        normalized = _as_probability(claimed)
    except (InvalidOperation, ValueError, ClaimGroundingError):
        return False
    actual_points = (actual * Decimal(100)).quantize(Decimal("0.1"))
    claimed_points = (normalized * Decimal(100)).quantize(Decimal("0.1"))
    return actual_points == claimed_points


def _signed_matches(claimed: str | float | bool, actual: Decimal) -> bool:
    try:
        normalized = _as_signed(claimed)
    except (InvalidOperation, ValueError, ClaimGroundingError):
        return False
    actual_points = (actual * Decimal(100)).quantize(Decimal("0.1"))
    claimed_points = (normalized * Decimal(100)).quantize(Decimal("0.1"))
    return actual_points == claimed_points or normalized.quantize(Decimal("0.001")) == actual.quantize(Decimal("0.001"))


def _as_probability(raw: str | float | bool) -> Decimal:
    value = _decimal(raw)
    if abs(value) > 1:
        value = value / Decimal(100)
    if value < 0 or value > 1:
        raise ClaimGroundingError(f"Probability value {raw} is outside [0, 1].")
    return value


def _as_signed(raw: str | float | bool) -> Decimal:
    value = _decimal(raw)
    if abs(value) > 1:
        return value / Decimal(100)
    return value


def _decimal(raw: str | float | bool) -> Decimal:
    if isinstance(raw, bool):
        raise ClaimGroundingError("Boolean is not a numeric claim value.")
    text = str(raw).strip().replace(",", ".").replace("+", "").replace("%", "")
    return Decimal(text)


def _looks_numeric(value: str | float) -> bool:
    if isinstance(value, int | float):
        return True
    try:
        _decimal(value)
        return True
    except (InvalidOperation, ValueError, ClaimGroundingError):
        return False


def _claim_subject(claim: GroundedClaim) -> str | None:
    if claim.subject is not None:
        return str(claim.subject)
    if claim.value is None:
        return None
    return str(claim.value)


def _relation_holds(left: Decimal, relation: ClaimRelation, right: Decimal) -> bool:
    if relation == "greater_than":
        return left > right
    if relation == "less_than":
        return left < right
    if relation == "equal":
        return left == right
    if relation == "greater_or_equal":
        return left >= right
    return left <= right


def _selection_label(context: AnalystContext, selection: Football1x2Selection) -> str:
    if selection is Football1x2Selection.HOME:
        return context.identity.home_team or "l'équipe à domicile"
    if selection is Football1x2Selection.AWAY:
        return context.identity.away_team or "l'équipe à l'extérieur"
    return "le match nul"


def _format_percent(value: Decimal) -> str:
    rendered = f"{(value * Decimal(100)):.1f}"
    return f"{rendered.replace('.', ',')} %"


def _format_points(value: Decimal) -> str:
    rendered = f"{(value * Decimal(100)):.1f}"
    signed = rendered if value < 0 else f"+{rendered}"
    return f"{signed.replace('.', ',')} points"


def _render_claim(context: AnalystContext, claim: GroundedClaim) -> str:
    if claim.claim_type == "model_probability":
        selection = resolve_subject(context, claim.subject)
        if selection is None:
            return ""
        return (
            f"Le modèle estime {_format_percent(context.prediction.probability(selection))} "
            f"de probabilité à {_selection_label(context, selection)}."
        )
    if claim.claim_type == "probability_comparison":
        return "La comparaison de probabilités modèle est cohérente avec le contexte validé."
    if claim.claim_type == "model_favorite":
        favorite = context.favorite_selection()
        return f"Le favori du modèle est {favorite.value} ({_selection_label(context, favorite)})."
    if claim.claim_type == "value_selection" and context.value_selection is not None:
        pick = context.value_selection
        return f"La sélection de valeur est {pick.value} ({_selection_label(context, pick)})."
    if claim.claim_type == "odds" and context.value is not None:
        return f"La cote PIT disponible est {context.value.odds}."
    if claim.claim_type == "implied_probability" and context.value is not None:
        return (
            "La probabilité implicite brute de la cote disponible est de "
            f"{_format_percent(context.value.implied_probability)}."
        )
    if claim.claim_type == "ev" and context.value is not None:
        return f"L'espérance théorique (EV) est de {_format_points(context.value.ev)}."
    if claim.claim_type == "edge" and context.value is not None:
        return f"L'écart modèle-marché (edge) est de {_format_points(context.value.edge)}."
    if claim.claim_type == "data_mode":
        return f"Ces faits sont servis en data_mode {context.data_mode} et ne doivent pas être présentés comme live."
    if claim.claim_type == "model_status":
        return (
            f"Le modèle {context.prediction.model_version} a le statut {context.prediction.model_status}, "
            "pas un statut de production promu."
        )
    return ""
