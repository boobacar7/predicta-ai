from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.ai_picks.models import AiPicksQuery
from app.api.deps import envelope, filter_market, get_container, paginate
from app.core.container import AppContainer
from app.schemas import AnalystRequest, MatchStatus, SportCode

router = APIRouter()


def _container(request: Request) -> AppContainer:
    return get_container(request)


@router.get("/dashboard")
def get_dashboard(request: Request) -> dict[str, object]:
    return envelope(request, _container(request).dashboard.snapshot())


@router.get("/sports")
def get_sports(request: Request) -> dict[str, object]:
    return envelope(request, _container(request).catalog.list_sports())


@router.get("/leagues")
def get_leagues(
    request: Request,
    sport: SportCode | None = None,
    query: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = _container(request).catalog.list_leagues(sport=sport, query=query)
    return envelope(request, paginate(items, limit=limit, offset=offset))


@router.get("/leagues/{league_id}")
def get_league(request: Request, league_id: str) -> dict[str, object]:
    return envelope(request, _container(request).catalog.get_league(league_id))


@router.get("/teams")
def get_teams(
    request: Request,
    sport: SportCode | None = None,
    query: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = _container(request).catalog.list_teams(sport=sport, query=query)
    return envelope(request, paginate(items, limit=limit, offset=offset))


@router.get("/teams/{team_id}")
def get_team(request: Request, team_id: str) -> dict[str, object]:
    return envelope(request, _container(request).catalog.get_team(team_id))


@router.get("/players")
def get_players(
    request: Request,
    sport: SportCode | None = None,
    query: str | None = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = _container(request).catalog.list_players(sport=sport, query=query)
    return envelope(request, paginate(items, limit=limit, offset=offset))


@router.get("/players/{player_id}")
def get_player(request: Request, player_id: str) -> dict[str, object]:
    return envelope(request, _container(request).catalog.get_player(player_id))


@router.get("/matches")
def get_matches(
    request: Request,
    sport: SportCode | None = None,
    league_id: str | None = Query(default=None, min_length=1, max_length=128),
    date: date | None = None,
    status: MatchStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    details = _container(request).matches.list_matches(sport=sport, league_id=league_id, match_date=date, status=status)
    from app.services.projections import to_match_summary

    items = [to_match_summary(item) for item in details]
    return envelope(request, paginate(items, limit=limit, offset=offset))


@router.get("/matches/{match_id}")
def get_match(request: Request, match_id: str) -> dict[str, object]:
    return envelope(request, _container(request).matches.get_match(match_id))


@router.get("/matches/{match_id}/stats")
def get_match_statistics(request: Request, match_id: str) -> dict[str, object]:
    match = _container(request).matches.get_match(match_id)
    return envelope(request, match.stats)


@router.get("/matches/{match_id}/odds")
def get_match_odds(
    request: Request,
    match_id: str,
    market: str | None = Query(default=None, min_length=1, max_length=64),
) -> dict[str, object]:
    match = _container(request).matches.get_match(match_id)
    return envelope(request, filter_market(match, market, "odds"))


@router.get("/matches/{match_id}/prediction")
def get_match_prediction(
    request: Request,
    match_id: str,
    market: str | None = Query(default=None, min_length=1, max_length=64),
) -> dict[str, object]:
    match = _container(request).matches.get_match(match_id)
    return envelope(request, filter_market(match, market, "prediction"))


@router.get("/football/predictions/{match_id}")
def get_football_model_prediction(
    request: Request,
    match_id: str,
    cutoff_at: Annotated[datetime | None, Query()] = None,
) -> dict[str, object]:
    prediction = _container(request).football_predictions().predict(match_id, cutoff_at)
    return envelope(request, prediction, data_mode="live")


@router.get("/football/value/{match_id}")
def get_football_match_value(
    request: Request,
    match_id: str,
    cutoff_at: Annotated[datetime | None, Query()] = None,
) -> dict[str, object]:
    analysis = _container(request).football_values().evaluate(match_id, cutoff_at)
    return envelope(request, analysis, data_mode=analysis.metadata.data_mode)


@router.get("/football/ai-picks")
def get_football_ai_picks(
    request: Request,
    date: date | None = None,
    league: str | None = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    min_edge: Annotated[Decimal | None, Query(ge=-1, lt=1)] = None,
    min_ev: Annotated[Decimal | None, Query(ge=-1)] = None,
) -> dict[str, object]:
    result = _container(request).football_ai_picks().list_picks(
        AiPicksQuery(
            match_date=date,
            league=league,
            limit=limit,
            offset=offset,
            minimum_edge=min_edge,
            minimum_ev=min_ev,
        )
    )
    return envelope(request, result)


@router.get("/picks")
def get_picks(
    request: Request,
    sport: SportCode | None = None,
    league_id: str | None = Query(default=None, min_length=1, max_length=128),
    date: date | None = None,
    status: MatchStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = _container(request).picks.list_picks(sport=sport, league_id=league_id, match_date=date, status=status)
    return envelope(request, paginate(items, limit=limit, offset=offset))


@router.get("/value")
def get_value(
    request: Request,
    sport: SportCode | None = None,
    league_id: str | None = Query(default=None, min_length=1, max_length=128),
    date: date | None = None,
    status: MatchStatus | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    items = _container(request).values.list_values(sport=sport, league_id=league_id, match_date=date, status=status)
    return envelope(request, paginate(items, limit=limit, offset=offset))


@router.get("/performance")
def get_performance(request: Request) -> dict[str, object]:
    return envelope(request, _container(request).performance.report())


@router.post("/ai/analyze")
def analyze(request: Request, body: AnalystRequest) -> dict[str, object]:
    session = _container(request).analyst.analyze(body.match_id, body.question)
    return envelope(request, session)
