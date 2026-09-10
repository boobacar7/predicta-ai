from datetime import datetime

import pytest

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import NaiveDateTimeError, ensure_utc, parse_rfc3339, to_rfc3339
from predicta_ingestion.raw.envelope import RawEnvelope


def test_rfc3339_roundtrip_is_utc() -> None:
    parsed = parse_rfc3339("2026-09-08T18:00:00+02:00")
    assert parsed.tzinfo is not None
    assert to_rfc3339(parsed) == "2026-09-08T16:00:00Z"


def test_raw_envelope_rejects_naive_collected_at() -> None:
    with pytest.raises((NaiveDateTimeError, ValueError)):
        RawEnvelope(
            provider="mock",
            resource=ResourceType.FIXTURES,
            request_key="x",
            collected_at=datetime(2026, 9, 8, 18, 0, 0),
            data_mode=DataMode.MOCK,
            sport=SportCode.FOOTBALL,
            body=b"{}",
        )


def test_ensure_utc_converts_offset(clock) -> None:
    value = parse_rfc3339("2026-09-09T18:00:00Z")
    assert ensure_utc(value) == clock.now()
