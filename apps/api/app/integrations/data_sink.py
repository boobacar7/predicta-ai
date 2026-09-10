"""SQL adapter for canonical ingestion objects. Does not call providers."""

from typing import Any, Protocol


class _HasProvenance(Protocol):
    provenance: Any


def provenance_columns(entity: _HasProvenance) -> dict[str, object]:
    provenance = entity.provenance
    return {
        "source": provenance.source,
        "collected_at": provenance.collected_at,
        "available_at": provenance.available_at,
        "data_mode": provenance.data_mode.value,
        "raw_payload_id": provenance.raw_payload_id,
    }
