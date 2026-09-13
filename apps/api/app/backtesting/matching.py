from __future__ import annotations

from datetime import datetime
from typing import Any

from app.backtesting.types import CatalogMatch, EventDecision, QualityExclusion, QualityLedger
from app.core.clock import parse_rfc3339
from app.predictions.runtime import ensure_ingestion_on_path

LIVE_ODDS_PROVIDER = "the_odds_api"


def football_natural_key(home: str, away: str, kickoff: datetime) -> str:
    ensure_ingestion_on_path()
    from predicta_ingestion.historical_odds import football_natural_key as _key

    return _key(home, away, kickoff)


def reverse_natural_key(key: str) -> str | None:
    parts = key.split("|")
    if len(parts) < 4:
        return None
    sport, home, away, kickoff = parts[0], parts[1], parts[2], "|".join(parts[3:])
    return f"{sport}|{away}|{home}|{kickoff}"


def classify_odds_event(event: dict[str, Any], catalog: tuple[CatalogMatch, ...]) -> EventDecision:
    """Exact key, then explicit alias. Isolated names and inverted 1X2 never match."""

    ensure_ingestion_on_path()
    from predicta_ingestion.identity.aliases import (
        apply_team_name_aliases,
        isolated_team_slugs,
    )
    from predicta_ingestion.ids import slugify

    event_id = str(event.get("id") or "")
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    kickoff = parse_rfc3339(str(event["commence_time"]))
    key = football_natural_key(home, away, kickoff)
    by_key = {football_natural_key(item.home_team, item.away_team, item.kickoff_at): item for item in catalog}

    exact = by_key.get(key)
    if exact is not None:
        return EventDecision(
            event_id=event_id,
            home_team=home,
            away_team=away,
            kickoff_at=kickoff,
            natural_key=key,
            status="exact",
            match_id=exact.match_id,
            detail="Odds event linked via football|home|away|kickoff.",
        )

    aliased = apply_team_name_aliases(key, LIVE_ODDS_PROVIDER)
    mapped = by_key.get(aliased)
    if mapped is not None and aliased != key:
        return EventDecision(
            event_id=event_id,
            home_team=home,
            away_team=away,
            kickoff_at=kickoff,
            natural_key=key,
            status="alias",
            match_id=mapped.match_id,
            detail="Odds event linked via explicit provider team alias.",
        )

    reversed_key = reverse_natural_key(key)
    reversed_aliased = apply_team_name_aliases(reversed_key, LIVE_ODDS_PROVIDER) if reversed_key else None
    inverted_hit = (reversed_key is not None and reversed_key in by_key) or (
        reversed_aliased is not None and reversed_aliased in by_key
    )
    if inverted_hit:
        return EventDecision(
            event_id=event_id,
            home_team=home,
            away_team=away,
            kickoff_at=kickoff,
            natural_key=key,
            status="inverted_home_away",
            match_id=None,
            detail="Home/away are inverted versus the canonical match; 1X2 is not matched.",
        )

    home_slug = slugify(home)
    away_slug = slugify(away)
    isolated = isolated_team_slugs()
    if home_slug in isolated or away_slug in isolated:
        return EventDecision(
            event_id=event_id,
            home_team=home,
            away_team=away,
            kickoff_at=kickoff,
            natural_key=key,
            status="isolated_team",
            match_id=None,
            detail="Isolated team name (Paris / Paris FC / PSG) is never aliased.",
        )

    return EventDecision(
        event_id=event_id,
        home_team=home,
        away_team=away,
        kickoff_at=kickoff,
        natural_key=key,
        status="unmatched",
        match_id=None,
        detail=f"No Sportmonks match for natural key '{key}'. Odds events never create canonical matches.",
    )


def decide_events(
    events: list[dict[str, Any]],
    catalog: tuple[CatalogMatch, ...],
    quality: QualityLedger,
) -> list[EventDecision]:
    seen: set[str] = set()
    decisions: list[EventDecision] = []
    for event in events:
        event_id = str(event.get("id") or "")
        if event_id in seen:
            continue
        seen.add(event_id)
        quality.events += 1
        decision = classify_odds_event(event, catalog)
        decisions.append(decision)
        if decision.status in {"exact", "alias"}:
            quality.matched += 1
            if decision.status == "exact":
                quality.exact_matches += 1
            else:
                quality.alias_matches += 1
        else:
            kind = {
                "isolated_team": "isolated_team",
                "inverted_home_away": "inverted_home_away",
                "unmatched": "unmatched_odds_event",
            }[decision.status]
            quality.add(
                QualityExclusion(
                    kind=kind,  # type: ignore[arg-type]
                    detail=decision.detail,
                    event_id=decision.event_id,
                )
            )
    return decisions
