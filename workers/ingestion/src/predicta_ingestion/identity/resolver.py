from __future__ import annotations

from dataclasses import dataclass

from predicta_ingestion.canonical.enums import DataMode, EntityType, ResolutionMethod
from predicta_ingestion.canonical.models import CanonicalBatch, League, OddsSnapshot, Provenance, Team
from predicta_ingestion.clock import Clock
from predicta_ingestion.identity.historical import provider_franchise_key
from predicta_ingestion.identity.keys import competition_slug, league_provider_key, team_name_key
from predicta_ingestion.quality.quarantine import QuarantineItem


@dataclass
class IdentityBinding:
    provider: str
    entity_type: EntityType
    provider_entity_id: str
    canonical_id: str
    method: ResolutionMethod
    confidence: float = 1.0
    name_key: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class IdentityDiagnostic:
    entity_type: str
    provider: str
    provider_entity_id: str
    provider_name: str | None
    canonical_id: str | None
    canonical_name: str | None
    resolution_method: str | None
    confidence: float | None
    status: str
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_type,
            "provider": self.provider,
            "provider_entity_id": self.provider_entity_id,
            "provider_name": self.provider_name,
            "canonical_id": self.canonical_id,
            "canonical_name": self.canonical_name,
            "resolution_method": self.resolution_method,
            "confidence": self.confidence,
            "status": self.status,
            "detail": self.detail,
        }


class IdentityResolver:
    """Maps provider ids to canonical ids. Ambiguous names are quarantined, never merged."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._by_provider: dict[tuple[str, str, str], IdentityBinding] = {}
        self._by_name: dict[tuple[str, str], set[str]] = {}
        self._by_franchise: dict[tuple[str, str], str] = {}
        self._canonical_names: dict[str, str] = {}
        self._by_match_key: dict[str, str] = {}
        self.diagnostics: list[IdentityDiagnostic] = []

    def lookup(self, provider: str, entity_type: EntityType, provider_entity_id: str) -> str | None:
        binding = self._by_provider.get((provider, entity_type.value, provider_entity_id))
        return None if binding is None else binding.canonical_id

    def bindings(self) -> list[IdentityBinding]:
        return list(self._by_provider.values())

    def unique_diagnostics(self) -> list[IdentityDiagnostic]:
        seen: dict[tuple[str, str, str, str], IdentityDiagnostic] = {}
        for item in self.diagnostics:
            key = (item.entity_type, item.provider_entity_id, item.status, item.detail)
            seen[key] = item
        return list(seen.values())

    def identity_report(self) -> list[IdentityDiagnostic]:
        items: list[IdentityDiagnostic] = []
        for item in self.unique_diagnostics():
            if item.status == "quarantined" or item.entity_type == "team":
                items.append(item)
        return items

    def resolve(self, batch: CanonicalBatch, *, data_mode: DataMode) -> list[QuarantineItem]:
        quarantined: list[QuarantineItem] = []
        leagues_by_id = {item.id: item for item in batch.leagues}
        for sport in batch.sports:
            self._bind(
                EntityType.SPORT,
                sport.provenance,
                sport.id,
                sport.name,
                quarantined,
                data_mode,
                display_name=sport.name,
            )
        for league in batch.leagues:
            name_key = f"{league.sport_id}:{league.name}:{league.season}"
            provider_id = league_provider_key(league.provenance.provider_id, league.season)
            provenance = league.provenance.model_copy(update={"provider_id": provider_id})
            self._bind(
                EntityType.LEAGUE,
                provenance,
                league.id,
                name_key,
                quarantined,
                data_mode,
                display_name=f"{league.name} {league.season}",
            )
        rewritten: dict[str, str] = {}
        for team in batch.teams:
            team_league = leagues_by_id.get(team.league_id)
            resolved = self._resolve_team(team, team_league, quarantined, data_mode)
            if resolved is not None and resolved != team.id:
                rewritten[team.id] = resolved
                team.id = resolved
        self._rewrite_team_ids(batch, rewritten)
        for player in batch.players:
            name_key = f"{player.sport_id}:{player.name}:{player.provenance.provider_id}"
            self._bind(
                EntityType.PLAYER,
                player.provenance,
                player.id,
                name_key,
                quarantined,
                data_mode,
                display_name=player.name,
            )
        for match in batch.matches:
            name_key = match.natural_key or match.id
            self._bind(
                EntityType.MATCH,
                match.provenance,
                match.id,
                name_key,
                quarantined,
                data_mode,
                display_name=match.natural_key,
            )
            if match.natural_key and match.natural_key not in self._by_match_key:
                self._by_match_key[match.natural_key] = match.id
        for snapshot in batch.odds:
            self._resolve_odds_match(snapshot)
        return quarantined

    def hydrate(self, bindings: list[IdentityBinding]) -> None:
        """Restore previously persisted maps so later competitions reuse canonical ids."""
        for binding in bindings:
            key = (binding.provider, binding.entity_type.value, binding.provider_entity_id)
            if key in self._by_provider:
                continue
            self._by_provider[key] = binding
            if binding.display_name and binding.canonical_id not in self._canonical_names:
                self._canonical_names[binding.canonical_id] = binding.display_name
            if binding.name_key:
                self._index_name(binding.entity_type, binding.name_key, binding.canonical_id)

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
                provider_name=name_key,
            )
        self._store_binding(
            provider=provider,
            entity_type=entity_type,
            provider_entity_id=provider_entity_id,
            canonical_id=canonical_id,
            method=ResolutionMethod.MANUAL,
            confidence=1.0,
            name_key=name_key,
            display_name=name_key,
        )
        return None

    def _resolve_team(
        self,
        team: Team,
        league: League | None,
        quarantined: list[QuarantineItem],
        data_mode: DataMode,
    ) -> str | None:
        name_key, aliased = team_name_key(team, league)
        competition = competition_slug(league)
        provider_id = team.provenance.provider_id
        existing = self._by_provider.get((team.provenance.provider, EntityType.TEAM.value, provider_id))
        if existing is not None:
            self._index_name(EntityType.TEAM, name_key, existing.canonical_id)
            self._record(
                entity_type="team",
                provider=team.provenance.provider,
                provider_entity_id=provider_id,
                provider_name=team.name,
                canonical_id=existing.canonical_id,
                canonical_name=self._canonical_names.get(existing.canonical_id, existing.display_name),
                method=existing.method,
                confidence=existing.confidence,
                status="resolved",
                detail="provider_id mapped to existing canonical id.",
            )
            return existing.canonical_id

        franchise = provider_franchise_key(competition, provider_id)
        if franchise is not None:
            mapped = self._by_franchise.get((competition, franchise))
            if mapped is not None:
                self._store_binding(
                    provider=team.provenance.provider,
                    entity_type=EntityType.TEAM,
                    provider_entity_id=provider_id,
                    canonical_id=mapped,
                    method=ResolutionMethod.HISTORICAL_ALIAS,
                    confidence=1.0,
                    name_key=name_key,
                    display_name=team.name,
                    franchise_key=(competition, franchise),
                )
                self._record(
                    entity_type="team",
                    provider=team.provenance.provider,
                    provider_entity_id=provider_id,
                    provider_name=team.name,
                    canonical_id=mapped,
                    canonical_name=self._canonical_names.get(mapped),
                    method=ResolutionMethod.HISTORICAL_ALIAS,
                    confidence=1.0,
                    status="resolved",
                    detail="Explicit historical provider id alias.",
                )
                return mapped

        name_ids = self._by_name.get((EntityType.TEAM.value, name_key), set())
        if len(name_ids) > 1:
            quarantined.append(
                self._ambiguous(
                    team.provenance.provider,
                    EntityType.TEAM,
                    provider_id,
                    data_mode,
                    "Normalized name is ambiguous.",
                    provider_name=team.name,
                    canonical_name=",".join(sorted(name_ids)),
                )
            )
            return None
        if len(name_ids) == 1:
            canonical_id = next(iter(name_ids))
            method = ResolutionMethod.HISTORICAL_ALIAS if aliased else ResolutionMethod.NORMALIZED_NAME
            confidence = 1.0 if aliased else 0.95
            self._store_binding(
                provider=team.provenance.provider,
                entity_type=EntityType.TEAM,
                provider_entity_id=provider_id,
                canonical_id=canonical_id,
                method=method,
                confidence=confidence,
                name_key=name_key,
                display_name=team.name,
                franchise_key=(competition, name_key.rsplit(":", 1)[-1]),
            )
            self._record(
                entity_type="team",
                provider=team.provenance.provider,
                provider_entity_id=provider_id,
                provider_name=team.name,
                canonical_id=canonical_id,
                canonical_name=self._canonical_names.get(canonical_id),
                method=method,
                confidence=confidence,
                status="resolved",
                detail="Unique normalized name mapped to existing canonical id.",
            )
            return canonical_id

        self._store_binding(
            provider=team.provenance.provider,
            entity_type=EntityType.TEAM,
            provider_entity_id=provider_id,
            canonical_id=team.id,
            method=ResolutionMethod.EXACT_ID,
            confidence=1.0,
            name_key=name_key,
            display_name=team.name,
            franchise_key=(competition, name_key.rsplit(":", 1)[-1]),
        )
        self._record(
            entity_type="team",
            provider=team.provenance.provider,
            provider_entity_id=provider_id,
            provider_name=team.name,
            canonical_id=team.id,
            canonical_name=team.name,
            method=ResolutionMethod.EXACT_ID,
            confidence=1.0,
            status="resolved",
            detail="New canonical id created from provider id.",
        )
        return team.id

    def _bind(
        self,
        entity_type: EntityType,
        provenance: Provenance,
        canonical_id: str,
        name_key: str,
        quarantined: list[QuarantineItem],
        data_mode: DataMode,
        *,
        display_name: str | None,
    ) -> str | None:
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
                        provider_name=display_name,
                        canonical_id=existing.canonical_id,
                        canonical_name=self._canonical_names.get(existing.canonical_id),
                    )
                )
                return None
            return existing.canonical_id
        name_ids = self._by_name.get((entity_type.value, name_key), set())
        if len(name_ids) > 1 or (name_ids and canonical_id not in name_ids):
            quarantined.append(
                self._ambiguous(
                    provenance.provider,
                    entity_type,
                    provenance.provider_id,
                    data_mode,
                    "Normalized name is ambiguous.",
                    provider_name=display_name,
                    canonical_name=",".join(sorted(name_ids)),
                )
            )
            return None
        self._store_binding(
            provider=provenance.provider,
            entity_type=entity_type,
            provider_entity_id=provenance.provider_id,
            canonical_id=canonical_id,
            method=ResolutionMethod.EXACT_ID,
            confidence=1.0,
            name_key=name_key,
            display_name=display_name,
        )
        return canonical_id

    def _store_binding(
        self,
        *,
        provider: str,
        entity_type: EntityType,
        provider_entity_id: str,
        canonical_id: str,
        method: ResolutionMethod,
        confidence: float,
        name_key: str,
        display_name: str | None,
        franchise_key: tuple[str, str] | None = None,
    ) -> None:
        self._by_provider[(provider, entity_type.value, provider_entity_id)] = IdentityBinding(
            provider=provider,
            entity_type=entity_type,
            provider_entity_id=provider_entity_id,
            canonical_id=canonical_id,
            method=method,
            confidence=confidence,
            name_key=name_key,
            display_name=display_name,
        )
        self._index_name(entity_type, name_key, canonical_id)
        if display_name and canonical_id not in self._canonical_names:
            self._canonical_names[canonical_id] = display_name
        if franchise_key is not None:
            self._by_franchise.setdefault(franchise_key, canonical_id)

    def _index_name(self, entity_type: EntityType, name_key: str, canonical_id: str) -> None:
        names = self._by_name.setdefault((entity_type.value, name_key), set())
        if names and canonical_id not in names:
            return
        names.add(canonical_id)

    def _rewrite_team_ids(self, batch: CanonicalBatch, rewritten: dict[str, str]) -> None:
        if not rewritten:
            return
        for match in batch.matches:
            if match.home_team_id in rewritten:
                match.home_team_id = rewritten[match.home_team_id]
            if match.away_team_id in rewritten:
                match.away_team_id = rewritten[match.away_team_id]
        for stats in batch.team_stats:
            if stats.team_id in rewritten:
                stats.team_id = rewritten[stats.team_id]
        for lineup in batch.lineups:
            if lineup.team_id in rewritten:
                lineup.team_id = rewritten[lineup.team_id]
        for event in batch.events:
            if event.team_id in rewritten:
                event.team_id = rewritten[event.team_id]
        for player in batch.players:
            if player.team_id in rewritten:
                player.team_id = rewritten[player.team_id]
        for injury in batch.injuries:
            if injury.team_id in rewritten:
                injury.team_id = rewritten[injury.team_id]

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
        *,
        provider_name: str | None = None,
        canonical_id: str | None = None,
        canonical_name: str | None = None,
    ) -> QuarantineItem:
        self._record(
            entity_type=entity_type.value,
            provider=provider,
            provider_entity_id=provider_id,
            provider_name=provider_name,
            canonical_id=canonical_id,
            canonical_name=canonical_name,
            method=None,
            confidence=None,
            status="quarantined",
            detail=detail,
        )
        return QuarantineItem(
            reason_code="ambiguous_identity",
            detail=detail,
            provider=provider,
            entity_type=entity_type.value,
            provider_entity_id=provider_id,
            data_mode=data_mode,
            created_at=self._clock.now(),
        )

    def _record(
        self,
        *,
        entity_type: str,
        provider: str,
        provider_entity_id: str,
        provider_name: str | None,
        canonical_id: str | None,
        canonical_name: str | None,
        method: ResolutionMethod | None,
        confidence: float | None,
        status: str,
        detail: str,
    ) -> None:
        self.diagnostics.append(
            IdentityDiagnostic(
                entity_type=entity_type,
                provider=provider,
                provider_entity_id=provider_entity_id,
                provider_name=provider_name,
                canonical_id=canonical_id,
                canonical_name=canonical_name,
                resolution_method=None if method is None else method.value,
                confidence=confidence,
                status=status,
                detail=detail,
            )
        )
