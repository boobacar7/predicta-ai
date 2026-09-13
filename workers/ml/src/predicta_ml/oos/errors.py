from __future__ import annotations

from predicta_ml.errors import PredictaMlError, TemporalLeakageError


class OosProtocolError(PredictaMlError):
    """The proposed evaluation window or artefact is incompatible with the frozen OOS protocol."""


class OosLeakageError(TemporalLeakageError):
    """A temporal leakage check failed. The backtest must not continue."""


class OosIdentityError(OosProtocolError):
    """Match identity is missing, duplicated, or otherwise ambiguous."""


class OosReproducibilityError(OosProtocolError):
    """Two evaluations of the same frozen inputs produced different results."""
