from datetime import date

from app.core.clock import Clock, to_rfc3339
from app.fixtures.quality import quality
from app.fixtures.store import FixtureStore, attach_picks, build_store
from app.repositories.protocols import CatalogRepository, MatchRepository, SignalRepository
from app.schemas import (
    Insight,
    League,
    LeagueDetail,
    MatchDetail,
    MatchStatus,
    NamedStat,
    PerformanceReport,
    Pick,
    Player,
    PlayerDetail,
    PredictionPreview,
    Sport,
    SportCode,
    StandingRow,
    Team,
    TeamDetail,
    UnavailableField,
)
from app.services.projections import to_match_summary
from app.services.value_service import value_preview_for_match


class MockCatalogRepository:
    def __init__(self, store: FixtureStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def list_sports(self) -> list[Sport]:
        return list(self._store.sports)

    def list_leagues(self, *, sport: SportCode | None, query: str | None) -> list[League]:
        return [item for item in self._store.leagues if _sport_ok(item.sport, sport) and _query_ok(item.name, query)]

    def get_league(self, league_id: str) -> LeagueDetail | None:
        league = next((item for item in self._store.leagues if item.id == league_id), None)
        if league is None:
            return None
        league_teams = [team for team in self._store.teams if team.league_id == league_id]
        standing = [
            StandingRow(
                rank=index + 1,
                team=team,
                played=6,
                points=15 - index * 2,
                goal_diff=8 - index * 3,
                quality=quality(self._clock, note="Classement fictif, non issu d'une compétition réelle."),
            )
            for index, team in enumerate(league_teams)
        ]
        recent = [to_match_summary(match) for match in self._store.matches if match.league.id == league_id][:4]
        missing = (
            [UnavailableField(field="standing", reason="Pas de classement d'équipe pour le tennis.")]
            if league.sport == "tennis"
            else []
        )
        return LeagueDetail(
            league=league,
            standing=[] if league.sport == "tennis" else standing,
            recent_matches=recent,
            unavailable_fields=missing,
        )

    def list_teams(self, *, sport: SportCode | None, query: str | None) -> list[Team]:
        return [item for item in self._store.teams if _sport_ok(item.sport, sport) and _query_ok(item.name, query)]

    def get_team(self, team_id: str) -> TeamDetail | None:
        team = next((item for item in self._store.teams if item.id == team_id), None)
        if team is None:
            return None
        league = next(item for item in self._store.leagues if item.id == team.league_id)
        recent = [
            to_match_summary(match)
            for match in self._store.matches
            if match.home.id == team_id or match.away.id == team_id
        ]
        return TeamDetail(
            team=team,
            league=league,
            recent_matches=recent,
            stats=[
                NamedStat(
                    key="elo",
                    label="Elo mock",
                    value=1512,
                    unit="rating",
                    quality=quality(self._clock, note="Rating fictif."),
                ),
                NamedStat(
                    key="injuries",
                    label="Blessures",
                    value=None,
                    unit=None,
                    quality=quality(
                        self._clock,
                        availability="unavailable",
                        note="Les blessures ne sont jamais inventées.",
                    ),
                ),
            ],
            unavailable_fields=[UnavailableField(field="injuries", reason="Les blessures ne sont jamais inventées.")],
        )

    def list_players(self, *, sport: SportCode | None, query: str | None) -> list[Player]:
        return [item for item in self._store.players if _sport_ok(item.sport, sport) and _query_ok(item.name, query)]

    def get_player(self, player_id: str) -> PlayerDetail | None:
        player = next((item for item in self._store.players if item.id == player_id), None)
        if player is None:
            return None
        team = next((item for item in self._store.teams if item.id == player.team_id), None)
        has_minutes = player.sport == "football"
        return PlayerDetail(
            player=player,
            team=team,
            stats=[
                NamedStat(
                    key="minutes",
                    label="Minutes mock",
                    value=412 if has_minutes else None,
                    unit="min",
                    quality=quality(
                        self._clock,
                        availability="available" if has_minutes else "unavailable",
                        note="Volume fictif." if has_minutes else "Non applicable dans ce sport mock.",
                    ),
                )
            ],
            recent_mentions=[],
            unavailable_fields=[UnavailableField(field="availability", reason="Disponibilité réelle non fournie.")],
        )


class MockMatchRepository:
    def __init__(self, store: FixtureStore) -> None:
        self._store = store

    def list_matches(
        self,
        *,
        sport: SportCode | None,
        league_id: str | None,
        match_date: date | None,
        status: MatchStatus | None,
    ) -> list[MatchDetail]:
        items: list[MatchDetail] = []
        for match in self._store.matches:
            if not _sport_ok(match.sport, sport):
                continue
            if league_id and match.league.id != league_id:
                continue
            if status and match.status != status:
                continue
            if match_date and to_rfc3339(match.kickoff_at)[:10] != match_date.isoformat():
                continue
            items.append(match)
        return items

    def get_match(self, match_id: str) -> MatchDetail | None:
        return next((item for item in self._store.matches if item.id == match_id), None)


class MockSignalRepository:
    def __init__(self, store: FixtureStore) -> None:
        self._store = store

    def list_picks(self) -> list[Pick]:
        return list(self._store.picks)

    def list_insights(self) -> list[Insight]:
        return list(self._store.insights)

    def get_performance(self) -> PerformanceReport:
        return self._store.performance


class MockRepositoryBundle:
    catalog: CatalogRepository
    matches: MatchRepository
    signals: SignalRepository

    def __init__(self, clock: Clock) -> None:
        store = build_store(clock)
        for match in store.matches:
            match.prediction_preview = _preview(match)
            match.value_preview = value_preview_for_match(match)
        summaries = {match.id: to_match_summary(match) for match in store.matches}
        attach_picks(store, clock, summaries)
        self.catalog = MockCatalogRepository(store, clock)
        self.matches = MockMatchRepository(store)
        self.signals = MockSignalRepository(store)


def _preview(match: MatchDetail) -> PredictionPreview | None:
    prediction = match.prediction
    if prediction is None:
        return None
    leading = max(
        prediction.outcomes,
        key=lambda item: item.calibrated_probability if item.calibrated_probability is not None else -1,
    )
    return PredictionPreview(
        model_version=prediction.model_version,
        market=prediction.market,
        confidence=prediction.confidence,
        leading_selection=leading.selection,
        leading_probability=leading.calibrated_probability,
        cutoff_at=prediction.cutoff_at,
        outcomes=prediction.outcomes,
        quality=prediction.quality,
    )


def _sport_ok(sport: SportCode, filter_sport: SportCode | None) -> bool:
    return filter_sport is None or sport == filter_sport


def _query_ok(name: str, query: str | None) -> bool:
    if not query:
        return True
    return query.casefold() in name.casefold()
