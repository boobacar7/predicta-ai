from __future__ import annotations

from app.predictions.exceptions import PitFeaturesUnavailableError
from app.schemas import DataMode

_LIVE: DataMode = "live"


def prediction_envelope_data_mode(feature_data_mode: str) -> DataMode:
    """Map PIT feature provenance onto the HTTP envelope without upgrading it.

    The candidate only accepts live historical rows. Mock features must fail
    closed instead of being advertised as live market data.
    """

    if feature_data_mode == _LIVE:
        return _LIVE
    if feature_data_mode == "mock":
        raise PitFeaturesUnavailableError(
            "Refusing non-live feature rows; mock features cannot drive the candidate."
        )
    raise PitFeaturesUnavailableError("Feature data_mode is missing or unsupported.")
