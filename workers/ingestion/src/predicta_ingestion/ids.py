from __future__ import annotations

import re
import unicodedata

PREFIXES = {
    "sport": "spt",
    "league": "lge",
    "team": "tm",
    "player": "plr",
    "match": "mth",
    "event": "evt",
    "odds": "odd",
    "raw": "raw",
    "run": "ing",
    "injury": "inj",
    "lineup": "lnp",
    "quarantine": "qtn",
    "standing": "std",
}


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    return slug or "unknown"


def canonical_id(prefix: str, *parts: str) -> str:
    body = "-".join(slugify(part) for part in parts if part)
    identifier = f"{prefix}_{body}" if body else prefix
    return identifier[:128]


def stable_entity_id(entity_type: str, *parts: str) -> str:
    return canonical_id(PREFIXES[entity_type], *parts)
