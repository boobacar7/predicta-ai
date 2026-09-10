from datetime import UTC, datetime, timedelta


class NaiveDateTimeError(ValueError):
    """Raised when a datetime lacks timezone information."""


def parse_rfc3339(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return ensure_utc(parsed)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise NaiveDateTimeError("Timestamps must be timezone-aware and are stored in UTC.")
    return value.astimezone(UTC)


def to_rfc3339(value: datetime) -> str:
    utc_value = ensure_utc(value).replace(microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


class Clock:
    """Injectable clock so mock fixtures and tests stay deterministic."""

    def __init__(self, now: datetime | None = None) -> None:
        self._fixed = ensure_utc(now) if now else None

    def now(self) -> datetime:
        if self._fixed is not None:
            return self._fixed
        return datetime.now(UTC)

    def shift(self, *, hours: int = 0, minutes: int = 0, days: int = 0) -> datetime:
        return self.now() + timedelta(days=days, hours=hours, minutes=minutes)
