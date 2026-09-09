from datetime import UTC, datetime, timedelta


def parse_rfc3339(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def to_rfc3339(value: datetime) -> str:
    utc_value = value.astimezone(UTC).replace(microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


class Clock:
    """Injectable clock so mock fixtures and tests stay deterministic."""

    def __init__(self, now: datetime | None = None) -> None:
        self._fixed = now.astimezone(UTC) if now else None

    def now(self) -> datetime:
        if self._fixed is not None:
            return self._fixed
        return datetime.now(UTC)

    def iso(self) -> str:
        return to_rfc3339(self.now())

    def shift(self, *, hours: int = 0, minutes: int = 0) -> datetime:
        return self.now() + timedelta(hours=hours, minutes=minutes)

    def iso_shift(self, *, hours: int = 0, minutes: int = 0) -> str:
        return to_rfc3339(self.shift(hours=hours, minutes=minutes))
