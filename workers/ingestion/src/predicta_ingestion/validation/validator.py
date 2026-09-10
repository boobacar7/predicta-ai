from __future__ import annotations

import json
from typing import Any

from predicta_ingestion.canonical.enums import DataMode
from predicta_ingestion.clock import NaiveDateTimeError, ensure_utc
from predicta_ingestion.config import Settings
from predicta_ingestion.errors import ValidationError
from predicta_ingestion.raw.store import StoredRaw


class Validator:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def validate(self, stored: StoredRaw, *, expected_mode: DataMode) -> dict[str, Any]:
        envelope = stored.envelope
        if len(envelope.body) > self._settings.max_payload_bytes:
            raise ValidationError("payload_too_large", "Raw payload exceeds the configured size limit.")
        if envelope.data_mode is DataMode.LIVE and expected_mode is DataMode.MOCK:
            raise ValidationError("data_mode_mismatch", "A live payload cannot be ingested in mock mode.")
        if envelope.data_mode is DataMode.MOCK and expected_mode is DataMode.LIVE:
            raise ValidationError("data_mode_mismatch", "A mock fixture cannot be advertised as live data.")
        try:
            ensure_utc(envelope.collected_at)
        except NaiveDateTimeError as exc:
            raise ValidationError("naive_datetime", str(exc)) from exc
        try:
            payload = json.loads(envelope.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("invalid_json", "Raw body is not valid JSON.") from exc
        if not isinstance(payload, dict):
            raise ValidationError("invalid_json", "Raw JSON root must be an object.")
        declared = payload.get("data_mode")
        if envelope.data_mode is DataMode.MOCK:
            if declared != DataMode.MOCK.value:
                raise ValidationError(
                    "data_mode_mismatch",
                    "Payload data_mode must match the envelope and cannot be omitted.",
                )
        elif declared == DataMode.MOCK.value:
            raise ValidationError(
                "data_mode_mismatch",
                "A mock fixture cannot be advertised as live data.",
            )
        return payload
