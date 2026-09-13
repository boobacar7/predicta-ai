from app.core.errors import ConflictError, UnprocessableError


class OddsUnavailableError(UnprocessableError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/odds-unavailable",
            title="Odds Unavailable",
        )


class IncompleteOddsMarketError(UnprocessableError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/incomplete-odds-market",
            title="Incomplete Odds Market",
        )


class OddsTemporalLeakageError(ConflictError):
    def __init__(self, detail: str) -> None:
        super().__init__(
            detail,
            type_uri="/problems/odds-temporal-leakage",
            title="Odds Temporal Leakage Refused",
        )
