class DataError(Exception):
    """Base error for the DATA layer."""


class ValidationError(DataError):
    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(detail)
        self.reason_code = reason_code
        self.detail = detail


class DataLeakageError(DataError):
    """Raised when a read would expose information after the cutoff."""


class DuplicateIdentityError(DataError):
    pass
