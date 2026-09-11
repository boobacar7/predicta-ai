from __future__ import annotations

import json

from app.ai_analyst.claims import ClaimGroundingError, validate_narrative_and_claims
from app.ai_analyst.models import ANALYST_PROVIDER_ID, LLM_ANALYST_PROVIDER_ID
from app.ai_analyst.statements import GroundedClaim, GroundedNarrative
from tests.test_ai_analyst_llm import _lincoln_context, _payload, _scripted
from tests.test_ai_analyst_redteam import AWAY_VALUE_CLAIM, HOME_FAVORITE_CLAIM, HOME_PROBABILITY_CLAIM


def _claims(*raw: dict[str, object]) -> tuple[GroundedClaim, ...]:
    return tuple(
        GroundedClaim(
            claim_type=item["claim_type"],  # type: ignore[arg-type]
            subject=item.get("subject"),  # type: ignore[arg-type]
            value=item.get("value"),  # type: ignore[arg-type]
            compare_to=item.get("compare_to"),  # type: ignore[arg-type]
            relation=item.get("relation"),  # type: ignore[arg-type]
            evidence_ids=tuple(item.get("evidence_ids") or ()),  # type: ignore[arg-type]
        )
        for item in raw
    )


def _validate(*raw: dict[str, object]) -> tuple[GroundedClaim, ...]:
    return validate_narrative_and_claims(
        _lincoln_context(),
        GroundedNarrative(narrative="The match appears open.", claims=_claims(*raw)),
    )


def _provider(claims: list[dict[str, object]], *, narrative: str = "The match appears open.") -> tuple[str, str | None]:
    provider = _scripted(_payload(narrative=narrative, claims=claims))
    explanation = provider.generate_analysis(_lincoln_context())
    return explanation.provider, provider.last_fallback_reason


def test_home_50_model_probability_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "model_probability",
                "subject": "HOME",
                "value": 0.50,
                "evidence_ids": ["prediction.home_probability"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID
    assert reason == "AnalystGroundingError"


def test_home_greater_than_50_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "probability_comparison",
                "subject": "HOME",
                "compare_to": 0.5,
                "relation": "greater_than",
                "evidence_ids": ["prediction.home_probability"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID
    assert reason == "AnalystGroundingError"


def test_home_greater_than_away_is_accepted_when_true() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "probability_comparison",
                "subject": "HOME",
                "compare_to": "AWAY",
                "relation": "greater_than",
                "evidence_ids": ["prediction.home_probability", "prediction.away_probability"],
            }
        ]
    )
    assert provider == LLM_ANALYST_PROVIDER_ID
    assert reason is None


def test_more_likely_than_not_is_rejected() -> None:
    try:
        _validate(
            {
                "claim_type": "probability_comparison",
                "subject": "HOME",
                "compare_to": 0.5,
                "relation": "greater_than",
                "evidence_ids": ["prediction.home_probability"],
            }
        )
    except ClaimGroundingError:
        return
    raise AssertionError("HOME > 0.5 must be rejected")


def test_away_more_likely_than_home_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "probability_comparison",
                "subject": "AWAY",
                "compare_to": "HOME",
                "relation": "greater_than",
                "evidence_ids": ["prediction.away_probability", "prediction.home_probability"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID
    assert reason == "AnalystGroundingError"


def test_favorite_away_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "model_favorite",
                "subject": "AWAY",
                "evidence_ids": ["prediction.model_favorite"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_best_value_home_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "value_selection",
                "subject": "HOME",
                "evidence_ids": ["value.value_selection"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_ev_away_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "ev",
                "subject": "AWAY",
                "value": -0.167,
                "evidence_ids": ["value.ev"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_odds_evidence_cannot_support_model_probability() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "model_probability",
                "subject": "HOME",
                "value": 0.417,
                "evidence_ids": ["value.odds"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_implied_evidence_cannot_support_model_probability() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "model_probability",
                "subject": "HOME",
                "value": 0.50,
                "evidence_ids": ["value.implied_probability"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_absent_team_is_rejected() -> None:
    provider, reason = _provider(
        [
            {
                "claim_type": "team",
                "subject": "PSG",
                "value": "PSG",
                "evidence_ids": ["identity.home_team"],
            }
        ]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_unsupported_sporting_claims_are_rejected() -> None:
    for claim_type in ("injury", "lineup", "result", "ranking"):
        provider, reason = _provider(
            [{"claim_type": claim_type, "subject": "HOME", "evidence_ids": ["identity.home_team"]}]
        )
        assert provider == ANALYST_PROVIDER_ID, claim_type
        assert reason == "AnalystGroundingError"


def test_mock_live_market_claim_is_rejected() -> None:
    provider, reason = _provider(
        [{"claim_type": "data_mode", "value": "live", "evidence_ids": ["metadata.data_mode"]}]
    )
    assert provider == ANALYST_PROVIDER_ID


def test_valid_model_probability_favorite_and_value_are_accepted() -> None:
    provider, reason = _provider([HOME_PROBABILITY_CLAIM, HOME_FAVORITE_CLAIM, AWAY_VALUE_CLAIM])
    assert provider == LLM_ANALYST_PROVIDER_ID
    assert reason is None


def test_qualitative_narrative_with_valid_claim_is_accepted() -> None:
    provider, reason = _provider(
        [HOME_FAVORITE_CLAIM],
        narrative="Le modèle présente un avantage pour l'équipe à domicile.",
    )
    assert provider == LLM_ANALYST_PROVIDER_ID
    assert reason is None


def test_qualitative_narrative_that_names_a_selection_is_rejected() -> None:
    provider, reason = _provider(
        [HOME_FAVORITE_CLAIM],
        narrative="AWAY is more likely than HOME",
    )
    assert provider == ANALYST_PROVIDER_ID


def test_malformed_unknown_and_invalid_evidence_fall_back() -> None:
    malformed = _scripted("{not-json")
    explanation = malformed.generate_analysis(_lincoln_context())
    assert explanation.provider == ANALYST_PROVIDER_ID
    unknown = _scripted(
        json.dumps(
            {
                "narrative": "The match appears open.",
                "claims": [
                    {
                        "claim_type": "made_up",
                        "subject": "HOME",
                        "evidence_ids": ["prediction.model_favorite"],
                    }
                ],
            }
        )
    )
    explanation = unknown.generate_analysis(_lincoln_context())
    assert explanation.provider == ANALYST_PROVIDER_ID
    invalid = _scripted(
        _payload(
            narrative="The match appears open.",
            claims=[
                {
                    "claim_type": "model_probability",
                    "subject": "HOME",
                    "value": 0.417,
                    "evidence_ids": ["prediction.nope"],
                }
            ],
        )
    )
    explanation = invalid.generate_analysis(_lincoln_context())
    assert explanation.provider == ANALYST_PROVIDER_ID
    assert invalid.last_fallback_reason == "AnalystGroundingError"


def test_runtimeerror_timeout_and_grounding_fall_back() -> None:
    runtime = _scripted(RuntimeError("provider down"))
    assert runtime.generate_analysis(_lincoln_context()).provider == ANALYST_PROVIDER_ID
    timeout = _scripted(_payload(narrative="The match appears open.", claims=[HOME_FAVORITE_CLAIM]), delay_seconds=1)
    assert timeout.generate_analysis(_lincoln_context()).provider == ANALYST_PROVIDER_ID
    grounding = _scripted(_payload(narrative="HOME is around fifty", claims=[]))
    assert grounding.generate_analysis(_lincoln_context()).provider == ANALYST_PROVIDER_ID
