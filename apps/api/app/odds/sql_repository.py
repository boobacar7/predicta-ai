from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db.models import OddsSelection as OddsSelectionRow
from app.db.models import OddsSnapshot as OddsSnapshotRow
from app.db.session import get_session_factory
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot


class SqlOddsRepository:
    """PostgreSQL append-only odds repository."""

    def __init__(self, settings: Settings) -> None:
        self._session_factory = get_session_factory(settings)

    def append(self, snapshot: OddsSnapshot) -> None:
        with self._session_factory() as session:
            existing = session.get(OddsSnapshotRow, snapshot.id)
            if existing is not None:
                if self._to_domain(existing) == snapshot:
                    return
                raise ValueError("Odds snapshots are immutable and cannot be overwritten.")
            row = OddsSnapshotRow(
                id=snapshot.id,
                provider_id=snapshot.provider_id,
                match_id=snapshot.match_id,
                market=snapshot.market,
                bookmaker=snapshot.bookmaker,
                provider=snapshot.source,
                observed_at=snapshot.collected_at,
                available_at=snapshot.available_at,
                collected_at=snapshot.collected_at,
                source=snapshot.source,
                freshness=None,
                data_mode=snapshot.data_mode,
                raw_payload_id=None,
                overround=None,
                created_at=snapshot.collected_at,
                selections=[
                    OddsSelectionRow(
                        selection=item.selection.value,
                        label=item.selection.value,
                        decimal_odds=item.decimal_odds,
                        implied_probability_raw=None,
                        no_vig_probability=None,
                    )
                    for item in snapshot.selections
                ],
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError as exc:
                session.rollback()
                raise ValueError(
                    "Odds provider_id already exists; snapshots cannot be overwritten."
                ) from exc

    def history(self, match_id: str, market: str) -> tuple[OddsSnapshot, ...]:
        statement = (
            select(OddsSnapshotRow)
            .where(
                OddsSnapshotRow.match_id == match_id,
                OddsSnapshotRow.market == market,
            )
            .options(selectinload(OddsSnapshotRow.selections))
            .order_by(
                OddsSnapshotRow.available_at,
                OddsSnapshotRow.collected_at,
                OddsSnapshotRow.id,
            )
        )
        with self._session_factory() as session:
            return tuple(self._to_domain(row) for row in session.scalars(statement))

    @staticmethod
    def _to_domain(row: OddsSnapshotRow) -> OddsSnapshot:
        return OddsSnapshot(
            id=row.id,
            provider_id=row.provider_id,
            match_id=row.match_id,
            bookmaker=row.bookmaker,
            market=row.market,
            selections=tuple(
                OddsSelection(
                    Football1x2Selection(item.selection),
                    Decimal(item.decimal_odds),
                )
                for item in row.selections
                if item.decimal_odds is not None
            ),
            collected_at=row.collected_at,
            available_at=row.available_at,
            source=row.source,
            data_mode=row.data_mode,  # type: ignore[arg-type]
        )
