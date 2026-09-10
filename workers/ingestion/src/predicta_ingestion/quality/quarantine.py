from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from predicta_ingestion.canonical.enums import DataMode


class QuarantineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: str
    detail: str
    provider: str
    entity_type: str
    data_mode: DataMode
    provider_entity_id: str | None = None
    raw_payload_id: str | None = None
    created_at: datetime
