from __future__ import annotations

from dataclasses import dataclass

from predicta_ingestion.canonical.enums import DataMode, EntityType, ResolutionMethod
from predicta_ingestion.canonical.models import CanonicalBatch, OddsSnapshot, Provenance
from predicta_ingestion.clock import Clock
from predicta_ingestion.quality.quarantine import QuarantineItem


@dataclass
class IdentityBinding:
    provider: str
    entity_type: EntityType
    provider_entity_id: str
    canonical_id: str
    method: ResolutionMethod
    name_key: str | None = None


class IdentityResolver:
    """Maps provider ids to canonical ids. Ambiguous names are quarantined, never merged."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._by_provider: dict[tuple[str, str, str], IdentityBinding] = {}
        self._by_name: dict[tuple[str, str], set[str]] = {}
        self._by_match_key: dict[str, str] = {}

    def lookup(self, provider: str, entity_type: EntityType, provider_entity_id: str) -> str | None:
        binding = self._by_provider.get((provider, entity_type.value, provider_entity_id))
        return None if binding is None else binding.canonical_id

    def resolve(self, batch: CanonicalBatch, *, data_mode: DataMode) -> list[QuarantineItem]:
        quarantined: list[QuarantineItem] = []
        for sport in batch.sports:
            self._bind(EntityType.SPORT, sport.provenance, sport.id, sport.name, quarantined, data_mode)
        for league in batch.leagues:
            name_key = f"{league.sport_id}:{league.name}:{league.season}"
            self._bind(EntityType.LEAGUE, league.provenance, league.id, name_key, quarantined, data_mode)
        for team in batch.teams:
            name_key = f"{team.league_id}:{team.name}"
            self._bind(EntityType.TEAM, team.provenance, team.id, name_key, quarantined, data_mode)
        for player in batch.players:
            name_key = f"{player.sport_id}:{player.name}:{player.provenance.provider_id}"
            self._bind(EntityType.PLAYER, player.provenance, player.id, name_key, quarantined, data_mode)
        for match in batch.matches:
            name_key = match.natural_key or match.id
            self._bind(EntityType.MATCH, match.provenance, match.id, name_key, quarantined, data_mode)
            if match.natural_key and match.natural_key not in self._by_match_key:
                self._by_match_key[match.natural_key] = match.id
        for snapshot in batch.odds:
            self._resolve_odds_match(snapshot)
        return quarantined

    def bind_explicit(
        self,
        *,
        provider: str,
        entity_type: EntityType,
        provider_entity_id: str,
        canonical_id: str,
        name_key: str,
        data_mode: DataMode,
    ) -> QuarantineItem | None:
        """Test helper and manual mapping entrypoint."""
        existing_names = self._by_name.get((entity_type.value, name_key), set())
        if existing_names and canonical_id not in existing_names:
            return self._ambiguous(
                provider,
                entity_type,
                provider_entity_id,
                data_mode,
                "Normalized name is ambiguous.",
            )
        self._by_provider[(provider, entity_type.value, provider_entity_id)] = IdentityBinding(
            provider=provider,
            entity_type=entity_type,
            provider_entity_id=provider_entity_id,
            canonical_id=canonical_id,
            method=ResolutionMethod.MANUAL,
            name_key=name_key,
        )
        self._by_name.setdefault((entity_type.value, name_key), set()).add(canonical_id)
        return None

    def _bind(
        self,
        entity_type: EntityType,
        provenance: Provenance,
        canonical_id: str,
        name_key: str,
        quarantined: list[QuarantineItem],
        data_mode: DataMode,
    ) -> None:
        key = (provenance.provider, entity_type.value, provenance.provider_id)
        existing = self._by_provider.get(key)
        if existing is not None:
            if existing.canonical_id != canonical_id:
                quarantined.append(
                    self._ambiguous(
                        provenance.provider,
                        entity_type,
                        provenance.provider_id,
                        data_mode,
                        "Provider id maps to multiple canonical ids.",
                    )
                )
            return
        name_ids = self._by_name.get((entity_type.value, name_key), set())
        if len(name_ids) > 1 or (name_ids and canonical_id not in name_ids):
            quarantined.append(
                self._ambiguous(
                    provenance.provider,
                    entity_type,
                    provenance.provider_id,
                    data_mode,
                    "Normalized name is ambiguous.",
                )
            )
            return
        self._by_provider[key] = IdentityBinding(
            provider=provenance.provider,
            entity_type=entity_type,
            provider_entity_id=provenance.provider_id,
            canonical_id=canonical_id,
            method=ResolutionMethod.EXACT_ID,
            name_key=name_key,
        )
        self._by_name.setdefault((entity_type.value, name_key), set()).add(canonical_id)

    def _resolve_odds_match(self, snapshot: OddsSnapshot) -> None:
        key = snapshot.match_natural_key
        if key and key in self._by_match_key:
            snapshot.match_id = self._by_match_key[key]

    def _ambiguous(
        self,
        provider: str,
        entity_type: EntityType,
        provider_id: str,
        data_mode: DataMode,
        detail: str,
    ) -> QuarantineItem:
        return QuarantineItem(
            reason_code="ambiguous_identity",
            detail=detail,
            provider=provider,
            entity_type=entity_type.value,
            provider_entity_id=provider_id,
            data_mode=data_mode,
            created_at=self._clock.now(),
        )
