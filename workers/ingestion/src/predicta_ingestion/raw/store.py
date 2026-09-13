from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol

from predicta_ingestion.canonical.enums import DataMode, SportCode
from predicta_ingestion.ids import canonical_id
from predicta_ingestion.raw.envelope import RawEnvelope, stable_checksum_bytes


class StoredRaw:
    def __init__(self, *, raw_id: str, envelope: RawEnvelope, storage_uri: str, duplicate: bool) -> None:
        self.id = raw_id
        self.envelope = envelope
        self.storage_uri = storage_uri
        self.duplicate = duplicate


class RawStore(Protocol):
    def put(self, envelope: RawEnvelope) -> StoredRaw: ...

    def get(self, raw_id: str) -> StoredRaw | None: ...

    def exists_checksum(self, provider: str, checksum: str) -> bool: ...


class FilesystemRawStore:
    """Immutable filesystem store. Same payload checksum is not overwritten."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._checksums: dict[tuple[str, str], str] = {}
        self._index_existing()

    def put(self, envelope: RawEnvelope) -> StoredRaw:
        checksum = envelope.checksum_sha256
        existing = self._checksums.get((envelope.provider, checksum))
        if existing is not None:
            stored = self.get(existing)
            if stored is not None:
                return StoredRaw(
                    raw_id=existing,
                    envelope=stored.envelope,
                    storage_uri=stored.storage_uri,
                    duplicate=True,
                )

        raw_id = canonical_id("raw", envelope.provider, envelope.resource, checksum[:12])
        existing_path = self._find_path(raw_id)
        if existing_path is not None:
            self._checksums[(envelope.provider, checksum)] = raw_id
            stored = self.get(raw_id)
            if stored is not None:
                return StoredRaw(
                    raw_id=raw_id,
                    envelope=stored.envelope,
                    storage_uri=str(existing_path),
                    duplicate=True,
                )

        collected = envelope.collected_at
        relative = (
            Path(envelope.data_mode.value)
            / envelope.provider
            / f"{collected:%Y}"
            / f"{collected:%m}"
            / f"{collected:%d}"
            / f"{raw_id}.json"
        )
        path = self._root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            self._checksums[(envelope.provider, checksum)] = raw_id
            return StoredRaw(raw_id=raw_id, envelope=envelope, storage_uri=str(path), duplicate=True)
        payload = {
            "id": raw_id,
            "provider": envelope.provider,
            "resource": envelope.resource.value,
            "request_key": envelope.request_key,
            "collected_at": collected.isoformat(),
            "data_mode": envelope.data_mode.value,
            "checksum_sha256": checksum,
            "content_type": envelope.content_type,
            "sport": envelope.sport.value if envelope.sport else None,
            "body_utf8": envelope.body.decode("utf-8"),
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._checksums[(envelope.provider, checksum)] = raw_id
        return StoredRaw(raw_id=raw_id, envelope=envelope, storage_uri=str(path), duplicate=False)

    def get(self, raw_id: str) -> StoredRaw | None:
        matches = list(self._root.rglob(f"{raw_id}.json"))
        if not matches:
            return None
        payload = json.loads(matches[0].read_text(encoding="utf-8"))
        envelope = RawEnvelope(
            provider=payload["provider"],
            resource=payload["resource"],
            request_key=payload["request_key"],
            collected_at=payload["collected_at"],
            data_mode=DataMode(payload["data_mode"]),
            body=payload["body_utf8"].encode("utf-8"),
            content_type=payload.get("content_type", "application/json"),
            sport=SportCode(payload["sport"]) if payload.get("sport") else None,
        )
        return StoredRaw(raw_id=raw_id, envelope=envelope, storage_uri=str(matches[0]), duplicate=False)

    def exists_checksum(self, provider: str, checksum: str) -> bool:
        return (provider, checksum) in self._checksums

    def _index_existing(self) -> None:
        if not self._root.exists():
            return
        for path in self._root.rglob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            provider = payload.get("provider")
            raw_id = payload.get("id")
            stored_checksum = payload.get("checksum_sha256")
            body = payload.get("body_utf8")
            if not isinstance(provider, str) or not isinstance(raw_id, str):
                continue
            if isinstance(stored_checksum, str):
                self._checksums[(provider, stored_checksum)] = raw_id
            if isinstance(body, str):
                current = hashlib.sha256(stable_checksum_bytes(body.encode("utf-8"))).hexdigest()
                self._checksums[(provider, current)] = raw_id

    def _find_path(self, raw_id: str) -> Path | None:
        matches = list(self._root.rglob(f"{raw_id}.json"))
        return matches[0] if matches else None
