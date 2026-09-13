from app.db.models import Injury, Lineup, Match, OddsSnapshot, RawPayload, Standing


def test_data_tables_expose_point_in_time_columns() -> None:
    assert hasattr(Match, "collected_at")
    assert hasattr(Match, "available_at")
    assert hasattr(Match, "data_mode")
    assert hasattr(OddsSnapshot, "available_at")
    assert OddsSnapshot.__table_args__[-2].name == "ck_odds_snapshots_data_mode"
    assert OddsSnapshot.__table_args__[-1].name == "ck_odds_snapshots_available_at"
    assert hasattr(RawPayload, "checksum_sha256")
    assert hasattr(Standing, "as_of")
    assert hasattr(Injury, "available_at")
    assert hasattr(Lineup, "observed_at")
