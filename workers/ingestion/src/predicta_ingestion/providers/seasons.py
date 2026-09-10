from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from predicta_ingestion.errors import ValidationError
from predicta_ingestion.providers.leagues import (
    EUROPEAN_HISTORY_SEASON_LIMIT,
    V1FootballLeague,
    is_mls,
)


@dataclass(frozen=True)
class DiscoveredSeason:
    provider_id: str
    name: str
    league_id: int
    starting_at: date | None
    ending_at: date | None
    is_current: bool
    finished: bool


def parse_discovered_seasons(payload: dict[str, Any], league: V1FootballLeague) -> list[DiscoveredSeason]:
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValidationError("invalid_payload", "Season discovery payload data must be a league object.")
    seasons = _as_list(data.get("seasons"))
    discovered: list[DiscoveredSeason] = []
    for item in seasons:
        if not isinstance(item, dict):
            continue
        provider_id = item.get("id")
        if provider_id is None or provider_id == "":
            raise ValidationError("missing_provider_id", "Season provider id is missing.")
        name = str(item.get("name") or "").strip()
        if not name:
            raise ValidationError("missing_season", "Season name is missing.")
        league_id = int(item.get("league_id") or data.get("id") or league.sportmonks_id)
        discovered.append(
            DiscoveredSeason(
                provider_id=str(provider_id),
                name=name,
                league_id=league_id,
                starting_at=_parse_date(item.get("starting_at")),
                ending_at=_parse_date(item.get("ending_at")),
                is_current=bool(item.get("is_current")),
                finished=bool(item.get("finished")),
            )
        )
    discovered.sort(key=lambda item: (item.ending_at or date.min, item.provider_id))
    return discovered


def select_seasons(
    discovered: list[DiscoveredSeason],
    *,
    league: V1FootballLeague,
    season: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    all_seasons: bool = False,
) -> list[DiscoveredSeason]:
    selected = list(discovered)
    if season:
        needle = season.strip()
        selected = [item for item in selected if item.provider_id == needle or item.name == needle]
        if not selected:
            known = ", ".join(item.name for item in discovered) or "(none returned by provider)"
            raise ValidationError(
                "unknown_season",
                f"Season '{season}' was not returned by Sportmonks for {league.name}. Known: {known}.",
            )
    if date_from is not None or date_to is not None:
        selected = [item for item in selected if _overlaps(item, date_from, date_to)]
    if not season and not all_seasons and not is_mls(league):
        selected = sorted(selected, key=lambda item: (item.ending_at or date.min, item.provider_id), reverse=True)
        selected = selected[:EUROPEAN_HISTORY_SEASON_LIMIT]
        selected.sort(key=lambda item: (item.ending_at or date.min, item.provider_id))
    return selected


def _overlaps(season: DiscoveredSeason, date_from: date | None, date_to: date | None) -> bool:
    start = season.starting_at or date.min
    end = season.ending_at or date.max
    window_start = date_from or date.min
    window_end = date_to or date.max
    return start <= window_end and end >= window_start


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        nested = value.get("data")
        if isinstance(nested, list):
            return nested
    return []


def _parse_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("naive_datetime", f"Unparseable season date '{value}'.") from exc
