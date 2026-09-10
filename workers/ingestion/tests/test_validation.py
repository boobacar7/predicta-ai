from datetime import datetime

import pytest

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import NaiveDateTimeError
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.raw.envelope import RawEnvelope
from predicta_ingestion.raw.store import StoredRaw
from predicta_ingestion.validation.validator import Validator


def _stored(body: bytes, collected_at: datetime | str = "2026-09-09T18:00:00Z") -> StoredRaw:
    envelope = RawEnvelope(
        provider="mock.api_football",
        resource=ResourceType.FIXTURES,
        request_key="test",
        collected_at=collected_at,
        data_mode=DataMode.MOCK,
        sport=SportCode.FOOTBALL,
        body=body,
    )
    return StoredRaw(raw_id="raw_test", envelope=envelope, storage_uri="memory", duplicate=False)


def test_rejects_invalid_json(settings: Settings) -> None:
    validator = Validator(settings)
    with pytest.raises(ValidationError) as exc:
        validator.validate(_stored(b"not-json"), expected_mode=DataMode.MOCK)
    assert exc.value.reason_code == "invalid_json"


def test_rejects_missing_data_mode(settings: Settings) -> None:
    validator = Validator(settings)
    with pytest.raises(ValidationError) as exc:
        validator.validate(_stored(b'{"response": []}'), expected_mode=DataMode.MOCK)
    assert exc.value.reason_code == "data_mode_mismatch"


def test_rejects_mock_payload_in_live_mode(settings: Settings) -> None:
    validator = Validator(settings)
    with pytest.raises(ValidationError) as exc:
        validator.validate(_stored(b'{"data_mode": "mock"}'), expected_mode=DataMode.LIVE)
    assert exc.value.reason_code == "data_mode_mismatch"


def test_live_payload_without_data_mode_is_accepted(settings: Settings) -> None:
    validator = Validator(settings)
    envelope = RawEnvelope(
        provider="sportmonks",
        resource=ResourceType.FIXTURES,
        request_key="sportmonks:test",
        collected_at="2026-09-09T18:00:00Z",
        data_mode=DataMode.LIVE,
        sport=SportCode.FOOTBALL,
        body=b'{"data": []}',
    )
    stored = StoredRaw(raw_id="raw_live", envelope=envelope, storage_uri="memory", duplicate=False)
    payload = validator.validate(stored, expected_mode=DataMode.LIVE)
    assert "data_mode" not in payload


def test_naive_datetime_is_rejected() -> None:
    from predicta_ingestion.clock import ensure_utc

    with pytest.raises(NaiveDateTimeError):
        ensure_utc(datetime(2026, 9, 9, 18, 0, 0))
