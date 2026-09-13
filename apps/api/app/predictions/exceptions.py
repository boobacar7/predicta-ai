from __future__ import annotations

from app.core.errors import ConflictError, ServiceUnavailableError, UnprocessableError


class ArtefactNotFoundError(ServiceUnavailableError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/model-artefact-not-found",
            title="Model Artefact Not Found",
        )


class PitFeaturesUnavailableError(UnprocessableError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/pit-features-unavailable",
            title="PIT Features Unavailable",
        )


class TemporalLeakageError(ConflictError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/temporal-leakage",
            title="Temporal Leakage Refused",
        )
