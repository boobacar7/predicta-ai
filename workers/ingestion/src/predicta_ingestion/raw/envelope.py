from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from predicta_ingestion.canonical.enums import DataMode, ResourceType, SportCode
from predicta_ingestion.clock import ensure_utc

_VOLATILE_JSON_KEYS = frozenset({"rate_limit", "subscription"})
_VOLATILE_PAGINATION_KEYS = frozenset({"next_cursor"})


class RawEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1)
    resource: ResourceType
    request_key: str = Field(min_length=1)
    collected_at: datetime
    data_mode: DataMode
    body: bytes
    content_type: str = "application/json"
    sport: SportCode | None = None
    headers: dict[str, str] = Field(default_factory=dict)

    @field_validator("collected_at")
    @classmethod
    def collected_utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @field_validator("headers")
    @classmethod
    def strip_secrets(cls, value: dict[str, str]) -> dict[str, str]:
        blocked = {"authorization", "x-rapidapi-key", "x-api-key", "api-key"}
        return {key: value[key] for key in value if key.lower() not in blocked}

    @property
    def checksum_sha256(self) -> str:
        return hashlib.sha256(stable_checksum_bytes(self.body)).hexdigest()

    def json_payload(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def stable_checksum_bytes(body: bytes) -> bytes:
    """Hash Sportmonks payloads without volatile quota/subscription metadata."""
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body
    if not isinstance(payload, dict):
        return body
    stable = {key: value for key, value in payload.items() if key not in _VOLATILE_JSON_KEYS}
    pagination = stable.get("pagination")
    if isinstance(pagination, dict):
        stable["pagination"] = {
            key: value for key, value in pagination.items() if key not in _VOLATILE_PAGINATION_KEYS
        }
    return json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
