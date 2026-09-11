"""Adversarial runner: attack LLMAnalystProvider with structured JSON, not regex lists."""

from __future__ import annotations

import json

from app.ai_analyst.models import ANALYST_PROVIDER_ID, LLM_ANALYST_PROVIDER_ID
from tests.test_ai_analyst_llm import _lincoln_context, _payload, _scripted
from tests.test_ai_analyst_redteam import HOME_FAVORITE_CLAIM, HOME_PROBABILITY_CLAIM

ATTACK_NARRATIVES = (
    "AWAY is more likely than HOME",
    "HOME is more likely than not",
    "the favorite is AWAY",
    "HOME is around 50",
    "HOME is around fifty",
    "HOME has high EV",
    "AWAY is more likely than HOME.",
    "Home is more likely than not",
    "The favorite is away",
    "HOME is around 50%",
    "HOME is roughly fifty percent",
    "HOME has a high expected value",
    "EV is high for HOME",
    "AWAY should be considered more likely",
    "HOME looks like a coin flip at 50",
)


def _attack(payload: dict[str, object]) -> tuple[str, str | None, str]:
    provider = _scripted(json.dumps(payload))
    explanation = provider.generate_analysis(_lincoln_context())
    return explanation.provider, provider.last_fallback_reason, explanation.summary


def test_adversarial_prose_without_claims_never_reaches_llm_provider() -> None:
    for narrative in ATTACK_NARRATIVES:
        provider, reason, summary = _attack({"narrative": narrative, "claims": []})
        assert provider == ANALYST_PROVIDER_ID, narrative
        assert reason is not None, narrative
        lowered = summary.casefold()
        assert "away is more likely than home" not in lowered
        assert "more likely than not" not in lowered
        assert "the favorite is away" not in lowered
        assert "around 50" not in lowered
        assert "around fifty" not in lowered
        assert "high ev" not in lowered


def test_adversarial_false_claims_never_reach_llm_provider() -> None:
    attacks: list[list[dict[str, object]]] = [
        [
            {
                "claim_type": "probability_comparison",
                "subject": "AWAY",
                "compare_to": "HOME",
                "relation": "greater_than",
                "evidence_ids": ["prediction.away_probability", "prediction.home_probability"],
            }
        ],
        [
            {
                "claim_type": "probability_comparison",
                "subject": "HOME",
                "compare_to": 0.5,
                "relation": "greater_than",
                "evidence_ids": ["prediction.home_probability"],
            }
        ],
        [{"claim_type": "model_favorite", "subject": "AWAY", "evidence_ids": ["prediction.model_favorite"]}],
        [
            {
                "claim_type": "model_probability",
                "subject": "HOME",
                "value": 0.50,
                "evidence_ids": ["prediction.home_probability"],
            }
        ],
        [
            {
                "claim_type": "model_probability",
                "subject": "HOME",
                "value": 50,
                "evidence_ids": ["prediction.home_probability"],
            }
        ],
        [
            {
                "claim_type": "ev",
                "subject": "HOME",
                "value": "high",
                "evidence_ids": ["value.ev"],
            }
        ],
        [
            {
                "claim_type": "model_probability",
                "subject": "HOME",
                "value": 0.417,
                "evidence_ids": ["value.odds"],
            }
        ],
    ]
    for claims in attacks:
        provider, reason, summary = _attack({"narrative": "The match appears open.", "claims": claims})
        assert provider == ANALYST_PROVIDER_ID, claims
        assert reason == "AnalystGroundingError"
        assert "away is more likely than home" not in summary.casefold()


def test_true_claims_cannot_smuggle_contradictory_prose() -> None:
    provider, reason, summary = _attack(
        {
            "narrative": "AWAY is more likely than HOME",
            "claims": [HOME_PROBABILITY_CLAIM, HOME_FAVORITE_CLAIM],
        }
    )
    assert provider == ANALYST_PROVIDER_ID
    assert reason == "AnalystGroundingError"
    assert "away is more likely than home" not in summary.casefold()


def test_valid_structured_pack_still_reaches_llm_provider() -> None:
    provider = _scripted(_payload(narrative="The match appears open.", claims=[HOME_FAVORITE_CLAIM]))
    explanation = provider.generate_analysis(_lincoln_context())
    assert explanation.provider == LLM_ANALYST_PROVIDER_ID
    assert provider.last_fallback_reason is None
