from __future__ import annotations

import re
from decimal import Decimal

from app.ai_analyst.context import AnalystContext
from app.ai_analyst.statements import ClaimType, GroundedClaim
from app.odds.types import Football1x2Selection

WORD_NUMBERS: dict[str, Decimal] = {
    "zero": Decimal("0"),
    "ten": Decimal("10"),
    "twenty": Decimal("20"),
    "thirty": Decimal("30"),
    "forty": Decimal("40"),
    "fifty": Decimal("50"),
    "sixty": Decimal("60"),
    "seventy": Decimal("70"),
    "eighty": Decimal("80"),
    "ninety": Decimal("90"),
    "hundred": Decimal("100"),
    "zéro": Decimal("0"),
    "dix": Decimal("10"),
    "vingt": Decimal("20"),
    "trente": Decimal("30"),
    "quarante": Decimal("40"),
    "cinquante": Decimal("50"),
    "soixante": Decimal("60"),
    "soixante-dix": Decimal("70"),
    "soixante dix": Decimal("70"),
    "quatre-vingt": Decimal("80"),
    "quatre-vingts": Decimal("80"),
    "quatre-vingt-dix": Decimal("90"),
    "cent": Decimal("100"),
}

MODEL_PROBABILITY_RE = re.compile(
    r"model(?:ed|led)?(?:\s+at)?(?:\s+probability)?|the model gives|model gives|"
    r"probabilit[ée]s? (?:modèle|modélisée|modeled)|plus haute probabilit[ée]|"
    r"probabilit[ée] supérieure|modèle (?:estime|donne|attribue)|probabilité modélisée",
    re.IGNORECASE,
)
HIGHEST_PROBABILITY_RE = re.compile(
    r"highest (?:model )?probability|plus haute probabilit[ée](?: modèle)?|"
    r"la plus haute probabilit[ée]|most likely|le plus probable",
    re.IGNORECASE,
)
FAVORITE_RE = re.compile(
    r"model favorite|favori du modèle|favorite du modèle|favori modèle|issue favorite",
    re.IGNORECASE,
)
BEST_VALUE_RE = re.compile(
    r"best value|meilleure valeur|meilleure value|value pick|best bet",
    re.IGNORECASE,
)
VALUE_SELECTION_RE = re.compile(
    r"value selection|value_selection|sélection de valeur",
    re.IGNORECASE,
)
RECOMMENDATION_RE = re.compile(
    r"\bi recommend\b|\brecommande(?:r)?\b|should be played|must be played|best bet|"
    r"pari recommandé",
    re.IGNORECASE,
)
INJURY_RE = re.compile(r"\b(?:injur(?:y|ed|ies)|hurt|bless(?:ure|é|ée|és|ées))\b", re.IGNORECASE)
LINEUP_RE = re.compile(r"\b(?:line[- ]?ups?|composition)\b", re.IGNORECASE)
RESULT_RE = re.compile(
    r"dernier résultat|last result|a gagné le match|won the match|final score|score final",
    re.IGNORECASE,
)
LIVE_AFFIRMATION_RE = re.compile(
    r"live markets?|live odds|cotes live|données live|uses live|using live|"
    r"marchés? live|real[- ]time (?:market|odds)|données en direct|(?<!pas )en direct",
    re.IGNORECASE,
)
LIVE_NEGATION_RE = re.compile(
    r"pas (?:être )?présenté(?:es)? comme live|not (?:be )?presented as live|"
    r"ne (?:doit|peuvent|peut) pas[^.]*live|not live|pas live",
    re.IGNORECASE,
)
COMPARATIVE_RE = re.compile(
    r"(?:above|over|more than|greater than|supérieure à|supérieur à|plus de)\s+"
    r"(\d+(?:[.,]\d+)?|seventy|eighty|ninety|soixante-dix|quatre-vingts?)",
    re.IGNORECASE,
)
PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|％|percent\b)", re.IGNORECASE)
NUMBER_RE = re.compile(r"(?<![\w.-])([+-]?\d+(?:[.,]\d+)?)(?![\w.])")
WORD_NUMBER_RE = re.compile(
    r"\b(" + "|".join(re.escape(word) for word in sorted(WORD_NUMBERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
IMPLIED_RE = re.compile(r"\b(?:implied|implicite)\b", re.IGNORECASE)
NO_VIG_RE = re.compile(r"no[_-]?vig|sans[_-]?marge|overround", re.IGNORECASE)
PROBABILITY_LANGUAGE_RE = re.compile(r"probabilit|percent|pour ?cent", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
CAMEL_NAME_RE = re.compile(r"\b([A-Z][a-zÀ-ÿ]+(?:[A-Z][a-zÀ-ÿ]+)+)\b")
TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ]+(?:-[A-Za-zÀ-ÿ]+)*")
TEAM_TOKEN_RE = re.compile(r"\bTeam\s+[A-Z0-9]+\b", re.IGNORECASE)

NARRATIVE_LEXICON = frozenset(
    {
        "a",
        "an",
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
        "for",
        "and",
        "but",
        "not",
        "nor",
        "or",
        "if",
        "to",
        "of",
        "in",
        "on",
        "at",
        "by",
        "as",
        "it",
        "its",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "has",
        "have",
        "had",
        "does",
        "do",
        "did",
        "no",
        "le",
        "la",
        "les",
        "un",
        "une",
        "des",
        "du",
        "de",
        "au",
        "aux",
        "et",
        "ou",
        "pas",
        "plus",
        "moins",
        "est",
        "sont",
        "ont",
        "dans",
        "pour",
        "par",
        "sur",
        "avec",
        "comme",
        "ce",
        "cet",
        "cette",
        "ces",
        "il",
        "elle",
        "ils",
        "elles",
        "eux",
        "nous",
        "vous",
        "ceci",
        "cela",
        "ceux",
        "home",
        "away",
        "draw",
        "nul",
        "model",
        "models",
        "modeled",
        "modelled",
        "modèle",
        "value",
        "values",
        "engine",
        "selection",
        "favorite",
        "favourite",
        "favori",
        "issue",
        "match",
        "league",
        "team",
        "probability",
        "probabilities",
        "probabilité",
        "probabilités",
        "percent",
        "percentage",
        "odds",
        "odd",
        "edge",
        "ev",
        "expected",
        "analysis",
        "analyst",
        "status",
        "statut",
        "version",
        "candidate",
        "candidat",
        "champion",
        "implied",
        "implicite",
        "theoretical",
        "théorique",
        "available",
        "disponible",
        "complete",
        "complète",
        "identity",
        "identité",
        "payload",
        "source",
        "sources",
        "data",
        "mode",
        "mock",
        "live",
        "cutoff",
        "market",
        "markets",
        "marché",
        "marchés",
        "estimate",
        "estimates",
        "estime",
        "gives",
        "give",
        "given",
        "donne",
        "attribue",
        "attribu",
        "indicate",
        "indicates",
        "confirm",
        "confirms",
        "confirment",
        "published",
        "qualitative",
        "uncertainty",
        "incertitude",
        "remains",
        "reste",
        "high",
        "medium",
        "low",
        "open",
        "ouvert",
        "appears",
        "paraît",
        "seem",
        "seems",
        "interpretative",
        "interprétatif",
        "statistical",
        "statistiques",
        "future",
        "futur",
        "result",
        "results",
        "résultat",
        "texte",
        "élevée",
        "elevated",
        "fait",
        "faits",
        "valeurs",
        "données",
        "espérance",
        "cote",
        "cotes",
        "analyse",
        "équipe",
        "domicile",
        "extérieur",
        "écart",
        "combine",
        "présenté",
        "présentées",
        "présentes",
        "contexte",
        "validé",
        "structurelle",
        "servi",
        "production",
        "marquées",
        "stale",
        "partial",
        "partielle",
        "explicitement",
        "indisponibles",
        "complétées",
        "modélisée",
        "brute",
        "calculée",
        "n",
        "l",
        "d",
        "none",
        "aucune",
        "aucun",
        "affirmée",
        "points",
        "point",
        "suivant",
        "suivantes",
        "métadonnées",
        "confiance",
        "limitée",
        "certitude",
        "estimations",
        "absente",
        "inventé",
        "manquant",
        "nom",
        "trois",
        "promu",
        "doivent",
        "doit",
        "peuvent",
        "peut",
        "être",
        "ne",
        "about",
        "environ",
        "above",
        "over",
        "more",
        "than",
        "greater",
        "supérieure",
        "supérieur",
        "highest",
        "haute",
        "most",
        "least",
        "best",
        "meilleure",
        "likely",
        "probable",
        "priced",
        "price",
        "prix",
        "visitor",
        "visiteur",
        "time",
        "real",
        "direct",
        "uses",
        "using",
        "identifiable",
        "servis",
        "facts",
        "fact",
        "note",
        "hello",
        "json",
        "pit",
        "http",
        "api",
        "dto",
        "id",
        "utc",
        "ai",
        "test",
        "mention",
        "mentions",
        "confirme",
        "favorise",
        "avantage",
        "buteur",
        "striker",
        "joueur",
        "player",
        "won",
        "gagné",
        "form",
        "www",
        "last",
        "three",
        "matches",
        "derniers",
        "matchs",
        "ranking",
        "classement",
        "standings",
        "hurt",
        "injured",
        "injury",
        "blessé",
        "blessure",
        "lineup",
        "composition",
        "recommend",
        "recommande",
        "played",
        "play",
        "pick",
        "bet",
        "mise",
        "pari",
        "safe",
        "sure",
        "win",
        "gain",
        "garanti",
        "guarantee",
        "certain",
        "possession",
        "shots",
        "target",
        "tirs",
        "cadrés",
        "xg",
        "goals",
        "score",
        "final",
        "été",
        "etes",
        "êtes",
        "avoir",
        "présentés",
        "realtime",
        "indique",
        "indiquent",
        "possède",
        "around",
        "nearly",
        "près",
    }
)

GENERIC_NAME_TOKENS = frozenset(
    {
        "fc",
        "cf",
        "sc",
        "afc",
        "club",
        "united",
        "city",
        "town",
        "the",
        "de",
        "del",
        "la",
        "le",
        "el",
        "and",
        "of",
    }
)
CONTEXT_INDEPENDENT_ENTITIES = frozenset(
    {
        "psg",
        "madrid",
        "barcelona",
        "barca",
        "atlantis",
        "paris",
        "germain",
        "realmadrid",
        "parissg",
    }
)

UNSUPPORTED_CLAIM_TYPES: frozenset[ClaimType] = frozenset(
    {"injury", "lineup", "result", "event", "statistic", "recommendation"}
)
EVIDENCE_FIELDS: dict[ClaimType, frozenset[str]] = {
    "model_probability": frozenset({"home_probability", "draw_probability", "away_probability"}),
    "model_favorite": frozenset({"model_favorite", "home_probability", "draw_probability", "away_probability"}),
    "value_selection": frozenset({"value_selection"}),
    "odds": frozenset({"odds"}),
    "implied_probability": frozenset({"implied_probability"}),
    "no_vig_probability": frozenset({"no_vig_probability"}),
    "ev": frozenset({"ev"}),
    "edge": frozenset({"edge"}),
    "data_mode": frozenset({"data_mode"}),
    "team": frozenset({"home_team", "away_team"}),
    "league": frozenset({"league"}),
}


class ClaimGroundingError(ValueError):
    """A narrative claim is incompatible with AnalystEvidence."""


def split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries without treating decimal points as terminators."""

    stripped = text.strip()
    if not stripped:
        return []
    return [part.strip() for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]


def extract_claims(
    text: str,
    context: AnalystContext,
    evidence_ids: tuple[str, ...] = (),
    *,
    masked_text: str | None = None,
) -> tuple[GroundedClaim, ...]:
    """Turn narrative into typed claims. Text itself is never a source of truth."""

    claims: list[GroundedClaim] = []
    topic_text = masked_text if masked_text is not None else text
    for sentence in split_sentences(text):
        subject = _primary_subject(context, sentence)
        claims.extend(_fact_claims(sentence, subject, evidence_ids))
    for sentence in split_sentences(topic_text):
        subject = _primary_subject(context, sentence)
        claims.extend(_topic_claims(sentence, subject, evidence_ids))
    claims.extend(_entity_claims(text, context, evidence_ids))
    return tuple(claims)


def validate_claims(
    context: AnalystContext,
    claims: tuple[GroundedClaim, ...],
    cited_fields: set[str],
) -> None:
    for claim in claims:
        _validate_claim(context, claim, cited_fields)


def mentioned_selections(context: AnalystContext, sentence: str) -> set[Football1x2Selection]:
    lowered = sentence.casefold()
    mentioned: set[Football1x2Selection] = set()
    home_labels = ["home", "domicile", *_identity_labels(context.identity.home_team)]
    away_labels = ["away", "extérieur", "visitor", "visiteur", *_identity_labels(context.identity.away_team)]
    if _labels_mentioned(lowered, home_labels):
        mentioned.add(Football1x2Selection.HOME)
    if _labels_mentioned(lowered, away_labels):
        mentioned.add(Football1x2Selection.AWAY)
    if any(label in lowered for label in ("draw", "nul", "match nul")):
        mentioned.add(Football1x2Selection.DRAW)
    return mentioned


def _labels_mentioned(lowered: str, labels: list[str]) -> bool:
    for label in labels:
        folded = label.casefold()
        if " " in folded:
            if folded in lowered:
                return True
            continue
        if re.search(rf"\b{re.escape(folded)}\b", lowered):
            return True
    return False


def _identity_labels(name: str | None) -> list[str]:
    if not name:
        return []
    labels = [name]
    for token in TOKEN_RE.findall(name):
        folded = token.casefold()
        if folded in GENERIC_NAME_TOKENS or folded in NARRATIVE_LEXICON:
            continue
        if len(folded) < 3:
            continue
        labels.append(token)
    return labels


def _topic_claims(
    sentence: str,
    subject: str | None,
    evidence_ids: tuple[str, ...],
) -> list[GroundedClaim]:
    claims: list[GroundedClaim] = []
    if INJURY_RE.search(sentence):
        claims.append(GroundedClaim("injury", subject, None, evidence_ids))
    if LINEUP_RE.search(sentence):
        claims.append(GroundedClaim("lineup", subject, None, evidence_ids))
    if RESULT_RE.search(sentence):
        claims.append(GroundedClaim("result", subject, None, evidence_ids))
    if RECOMMENDATION_RE.search(sentence):
        claims.append(GroundedClaim("recommendation", subject, None, evidence_ids))
    if LIVE_AFFIRMATION_RE.search(sentence) and not LIVE_NEGATION_RE.search(sentence):
        claims.append(GroundedClaim("data_mode", None, "live", evidence_ids))
    return claims


def _fact_claims(
    sentence: str,
    subject: str | None,
    evidence_ids: tuple[str, ...],
) -> list[GroundedClaim]:
    claims: list[GroundedClaim] = []
    lowered = sentence.casefold()
    denied = "aucune" in lowered or "n'est affirmée" in lowered or "n’est affirmée" in lowered
    if FAVORITE_RE.search(sentence) or HIGHEST_PROBABILITY_RE.search(sentence):
        claims.append(GroundedClaim("model_favorite", subject, subject, evidence_ids))
    if BEST_VALUE_RE.search(sentence) or VALUE_SELECTION_RE.search(sentence):
        claims.append(GroundedClaim("value_selection", subject, subject, evidence_ids))
    magnitudes = _magnitude_values(sentence)
    if not denied and IMPLIED_RE.search(sentence):
        for value in magnitudes:
            claims.append(GroundedClaim("implied_probability", subject, float(value), evidence_ids))
        if not magnitudes:
            claims.append(GroundedClaim("implied_probability", subject, None, evidence_ids))
    elif NO_VIG_RE.search(sentence):
        for value in magnitudes:
            claims.append(GroundedClaim("no_vig_probability", subject, float(value), evidence_ids))
    elif _is_model_probability_sentence(sentence):
        for value in magnitudes:
            claims.append(GroundedClaim("model_probability", subject, float(value), evidence_ids))
        if not magnitudes and not FAVORITE_RE.search(sentence) and not HIGHEST_PROBABILITY_RE.search(sentence):
            claims.append(GroundedClaim("model_probability", subject, None, evidence_ids))
    if not denied and re.search(r"\b(?:ev|espérance)\b", sentence, re.IGNORECASE):
        values = _signed_values(sentence)
        if values:
            for value in values:
                claims.append(GroundedClaim("ev", subject, float(value), evidence_ids))
        else:
            claims.append(GroundedClaim("ev", subject, None, evidence_ids))
    if not denied and re.search(r"\bedge\b", sentence, re.IGNORECASE):
        values = _signed_values(sentence)
        if values:
            for value in values:
                claims.append(GroundedClaim("edge", subject, float(value), evidence_ids))
        else:
            claims.append(GroundedClaim("edge", subject, None, evidence_ids))
    return claims


def _entity_claims(
    text: str,
    context: AnalystContext,
    evidence_ids: tuple[str, ...],
) -> list[GroundedClaim]:
    allowed = _allowed_name_tokens(context)
    claims: list[GroundedClaim] = []
    for camel in CAMEL_NAME_RE.findall(text):
        compact = _compact(camel)
        if compact not in allowed and not _name_in_allowed(camel, allowed):
            claims.append(GroundedClaim("team", camel, camel, evidence_ids))
    for token in TOKEN_RE.findall(text):
        folded = token.casefold()
        if folded in WORD_NUMBERS or folded.replace("-", " ") in WORD_NUMBERS:
            continue
        if folded in allowed or _name_in_allowed(token, allowed):
            continue
        if "-" in folded and all(
            part in NARRATIVE_LEXICON or part in allowed or part in WORD_NUMBERS for part in folded.split("-")
        ):
            continue
        if folded in NARRATIVE_LEXICON and folded not in CONTEXT_INDEPENDENT_ENTITIES:
            continue
        if folded in CONTEXT_INDEPENDENT_ENTITIES or len(folded) >= 3:
            claims.append(GroundedClaim("team", token, token, evidence_ids))
    for match in TEAM_TOKEN_RE.findall(text):
        if match.casefold() not in allowed:
            claims.append(GroundedClaim("team", match, match, evidence_ids))
    return claims


def _validate_claim(context: AnalystContext, claim: GroundedClaim, cited_fields: set[str]) -> None:
    if claim.claim_type in UNSUPPORTED_CLAIM_TYPES:
        raise ClaimGroundingError(f"Unsupported claim type '{claim.claim_type}' is not present in AnalystEvidence.")
    if claim.claim_type == "data_mode" and claim.value == "live" and context.data_mode != "live":
        raise ClaimGroundingError("Narrative presents mock data_mode as live.")
    if claim.claim_type == "model_probability":
        _validate_model_probability(context, claim, cited_fields)
        return
    if claim.claim_type in {"implied_probability", "no_vig_probability"}:
        _validate_market_percent(context, claim, cited_fields)
        return
    if claim.claim_type == "model_favorite":
        _validate_favorite(context, claim, cited_fields)
        return
    if claim.claim_type == "value_selection":
        _validate_value_selection(context, claim, cited_fields)
        return
    if claim.claim_type in {"ev", "edge"}:
        _validate_signed_metric(context, claim, cited_fields)
        return
    if claim.claim_type == "team":
        if not _name_in_allowed(str(claim.value or claim.subject or ""), _allowed_name_tokens(context)):
            raise ClaimGroundingError(f"Entity '{claim.subject}' is not present in AnalystContext.")
        return
    required = EVIDENCE_FIELDS.get(claim.claim_type)
    if required and cited_fields and not cited_fields.intersection(required):
        raise ClaimGroundingError(f"Claim '{claim.claim_type}' is not supported by cited evidence.")


def _validate_model_probability(
    context: AnalystContext,
    claim: GroundedClaim,
    cited_fields: set[str],
) -> None:
    required = EVIDENCE_FIELDS["model_probability"]
    if cited_fields and not cited_fields.intersection(required):
        raise ClaimGroundingError("Model probability claim is not supported by cited evidence.")
    if claim.value is None:
        return
    expected = _model_percent_for_subject(context, claim.subject)
    actual = Decimal(str(claim.value)).quantize(Decimal("0.1"))
    if expected is not None and actual not in expected:
        raise ClaimGroundingError(f"Model-probability value {claim.value} is incompatible with AnalystEvidence.")
    if expected is None:
        allowed = _all_model_percents(context)
        if actual not in allowed:
            raise ClaimGroundingError(f"Model-probability value {claim.value} is incompatible with AnalystEvidence.")


def _validate_favorite(context: AnalystContext, claim: GroundedClaim, cited_fields: set[str]) -> None:
    favorite = context.favorite_selection().value
    if claim.subject and claim.subject != favorite:
        raise ClaimGroundingError("Narrative presents a non-favorite as the model favorite.")
    required = EVIDENCE_FIELDS["model_favorite"]
    if cited_fields and not cited_fields.intersection(required):
        raise ClaimGroundingError("Model favorite claim is not supported by cited evidence.")


def _validate_market_percent(
    context: AnalystContext,
    claim: GroundedClaim,
    cited_fields: set[str],
) -> None:
    required = EVIDENCE_FIELDS[claim.claim_type]
    if cited_fields and not cited_fields.intersection(required):
        raise ClaimGroundingError(f"{claim.claim_type} claim is not supported by cited evidence.")
    if context.value is None:
        raise ClaimGroundingError(f"{claim.claim_type} claim is unavailable in AnalystContext.")
    owner = context.value.selection.value
    if claim.subject and claim.subject != owner:
        raise ClaimGroundingError(f"{claim.claim_type} claim is attributed to the wrong selection.")
    if claim.value is None:
        return
    raw = (
        context.value.implied_probability
        if claim.claim_type == "implied_probability"
        else context.value.no_vig_probability
    )
    percent = (raw * Decimal(100)).quantize(Decimal("0.1"))
    actual = Decimal(str(claim.value)).quantize(Decimal("0.1"))
    if actual not in {percent, abs(percent)}:
        raise ClaimGroundingError(f"{claim.claim_type} value is incompatible with AnalystEvidence.")


def _validate_value_selection(context: AnalystContext, claim: GroundedClaim, cited_fields: set[str]) -> None:
    if context.value_selection is None:
        raise ClaimGroundingError("Value selection claim is unavailable in AnalystContext.")
    expected = context.value_selection.value
    if claim.subject and claim.subject != expected:
        raise ClaimGroundingError("Narrative presents a non-value selection as the best value.")
    if cited_fields and "value_selection" not in cited_fields:
        raise ClaimGroundingError("Value selection claim is not supported by cited evidence.")


def _validate_signed_metric(context: AnalystContext, claim: GroundedClaim, cited_fields: set[str]) -> None:
    required = EVIDENCE_FIELDS[claim.claim_type]
    if cited_fields and not cited_fields.intersection(required):
        raise ClaimGroundingError(f"{claim.claim_type} claim is not supported by cited evidence.")
    if context.value is None:
        raise ClaimGroundingError(f"{claim.claim_type} claim is unavailable in AnalystContext.")
    owner = context.value.selection.value
    if claim.subject and claim.subject != owner:
        raise ClaimGroundingError(f"{claim.claim_type} claim is attributed to the wrong selection.")
    if claim.value is None:
        return
    raw = context.value.ev if claim.claim_type == "ev" else context.value.edge
    points = (raw * Decimal(100)).quantize(Decimal("0.1"))
    actual = Decimal(str(claim.value)).quantize(Decimal("0.1"))
    if actual not in {points, abs(points), raw.quantize(Decimal("0.001"))}:
        raise ClaimGroundingError(f"{claim.claim_type} value {claim.value} is incompatible with AnalystEvidence.")


def _primary_subject(context: AnalystContext, sentence: str) -> str | None:
    mentioned = mentioned_selections(context, sentence)
    if len(mentioned) == 1:
        return next(iter(mentioned)).value
    if Football1x2Selection.AWAY in mentioned and Football1x2Selection.HOME not in mentioned:
        return Football1x2Selection.AWAY.value
    if Football1x2Selection.HOME in mentioned:
        return Football1x2Selection.HOME.value
    if mentioned:
        return next(iter(mentioned)).value
    return None


def _is_model_probability_sentence(sentence: str) -> bool:
    if IMPLIED_RE.search(sentence) or NO_VIG_RE.search(sentence):
        return False
    if re.search(r"\b(?:ev|espérance|edge)\b", sentence, re.IGNORECASE):
        return False
    if re.search(r"(?:odds|cote|priced at|price of|prix de)", sentence, re.IGNORECASE):
        return False
    return bool(
        MODEL_PROBABILITY_RE.search(sentence)
        or PROBABILITY_LANGUAGE_RE.search(sentence)
        or COMPARATIVE_RE.search(sentence)
        or PERCENT_RE.search(sentence)
    )


def _magnitude_values(sentence: str) -> list[Decimal]:
    values: list[Decimal] = []
    seen: set[Decimal] = set()

    def add(value: Decimal) -> None:
        if value not in seen:
            seen.add(value)
            values.append(value)

    for raw in PERCENT_RE.findall(sentence):
        add(_to_decimal(raw))
    for match in COMPARATIVE_RE.finditer(sentence):
        add(_to_decimal_or_word(match.group(1)))
    if (
        COMPARATIVE_RE.search(sentence)
        or PROBABILITY_LANGUAGE_RE.search(sentence)
        or MODEL_PROBABILITY_RE.search(sentence)
        or IMPLIED_RE.search(sentence)
    ):
        for match in WORD_NUMBER_RE.finditer(sentence):
            add(_to_decimal_or_word(match.group(1)))
    return values


def _signed_values(sentence: str) -> list[Decimal]:
    values: list[Decimal] = []
    for raw in PERCENT_RE.findall(sentence):
        values.append(_to_decimal(raw))
    for raw in NUMBER_RE.findall(sentence):
        values.append(_to_decimal(raw))
    return values


def _model_percent_for_subject(context: AnalystContext, subject: str | None) -> set[Decimal] | None:
    mapping = {
        "HOME": context.prediction.home_probability,
        "AWAY": context.prediction.away_probability,
        "DRAW": context.prediction.draw_probability,
    }
    if subject not in mapping:
        return None
    percent = (mapping[subject] * Decimal(100)).quantize(Decimal("0.1"))
    return {percent, abs(percent)}


def _all_model_percents(context: AnalystContext) -> set[Decimal]:
    allowed: set[Decimal] = set()
    for value in (
        context.prediction.home_probability,
        context.prediction.draw_probability,
        context.prediction.away_probability,
    ):
        percent = (value * Decimal(100)).quantize(Decimal("0.1"))
        allowed.add(percent)
        allowed.add(abs(percent))
    return allowed


def _allowed_name_tokens(context: AnalystContext) -> set[str]:
    names = {
        context.identity.league.casefold(),
        context.prediction.model_version.casefold(),
        context.prediction.dataset_version.casefold(),
        "home",
        "away",
        "draw",
    }
    if context.identity.home_team:
        names.add(context.identity.home_team.casefold())
    if context.identity.away_team:
        names.add(context.identity.away_team.casefold())
    if context.value is not None:
        names.add(context.value.value_engine_version.casefold())
    tokens: set[str] = set()
    for name in names:
        tokens.add(name)
        tokens.add(_compact(name))
        tokens.update(TOKEN_RE.findall(name))
    return tokens


def _name_in_allowed(name: str, allowed: set[str]) -> bool:
    folded = name.casefold()
    compact = _compact(name)
    if folded in allowed or compact in allowed:
        return True
    return any(re.search(rf"\b{re.escape(folded)}\b", candidate) for candidate in allowed)


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _to_decimal(raw: str) -> Decimal:
    return Decimal(raw.replace(",", ".").replace("+", ""))


def _to_decimal_or_word(raw: str) -> Decimal:
    folded = raw.casefold().replace("  ", " ")
    if folded in WORD_NUMBERS:
        return WORD_NUMBERS[folded]
    return _to_decimal(raw)
