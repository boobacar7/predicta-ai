from app.core.errors import UnprocessableError


class InvalidPredictionError(UnprocessableError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/invalid-prediction",
            title="Invalid Prediction",
        )
