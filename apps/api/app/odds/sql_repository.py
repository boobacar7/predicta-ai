from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings
from app.db.models import OddsSelection as OddsSelectionRow
from app.db.models import OddsSnapshot as OddsSnapshotRow
from app.db.session import get_session_factory
from app.odds.types import DataMode, Football1x2Selection, OddsSelection, OddsSnapshot

_SELECTION_ORDER = {selection: index for index, selection in enumerate(Football1x2Selection)}


class SqlOddsRepository:
    """PostgreSQL append-only odds repository."""

    def __init__(self, settings: Settings) -> None:
        self._session_factory = get_session_factory(settings)

    def append(self, snapshot: OddsSnapshot) -> None:
        with self._session_factory() as session:
            existing = session.get(
                OddsSnapshotRow,
                snapshot.id,
                options=(selectinload(OddsSnapshotRow.selections),),
            )
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
                raw_payload_id=snapshot.raw_payload_id,
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
                persisted = self._existing_row(session, snapshot)
                if persisted is not None and self._to_domain(persisted) == snapshot:
                    return
                raise ValueError(
                    "Odds provider_id already exists; snapshots cannot be overwritten."
                ) from exc

    def history(
        self,
        match_id: str,
        market: str,
        *,
        source: str | None = None,
        data_mode: DataMode | None = None,
    ) -> tuple[OddsSnapshot, ...]:
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
        if source is not None:
            statement = statement.where(OddsSnapshotRow.source == source)
        if data_mode is not None:
            statement = statement.where(OddsSnapshotRow.data_mode == data_mode)
        with self._session_factory() as session:
            return tuple(self._to_domain(row) for row in session.scalars(statement))

    def history_many(
        self,
        match_ids: Sequence[str],
        market: str,
        *,
        source: str | None = None,
        data_mode: DataMode | None = None,
    ) -> tuple[OddsSnapshot, ...]:
        if not match_ids:
            return ()
        statement = (
            select(OddsSnapshotRow)
            .where(
                OddsSnapshotRow.match_id.in_(list(match_ids)),
                OddsSnapshotRow.market == market,
            )
            .options(selectinload(OddsSnapshotRow.selections))
            .order_by(
                OddsSnapshotRow.match_id,
                OddsSnapshotRow.available_at,
                OddsSnapshotRow.collected_at,
                OddsSnapshotRow.id,
            )
        )
        if source is not None:
            statement = statement.where(OddsSnapshotRow.source == source)
        if data_mode is not None:
            statement = statement.where(OddsSnapshotRow.data_mode == data_mode)
        with self._session_factory() as session:
            return tuple(self._to_domain(row) for row in session.scalars(statement))

    @staticmethod
    def _existing_row(session: Session, snapshot: OddsSnapshot) -> OddsSnapshotRow | None:
        existing = session.get(
            OddsSnapshotRow,
            snapshot.id,
            options=(selectinload(OddsSnapshotRow.selections),),
        )
        if existing is not None:
            return existing
        statement = (
            select(OddsSnapshotRow)
            .where(
                OddsSnapshotRow.provider == snapshot.source,
                OddsSnapshotRow.provider_id == snapshot.provider_id,
            )
            .options(selectinload(OddsSnapshotRow.selections))
        )
        return session.scalar(statement)

    @staticmethod
    def _to_domain(row: OddsSnapshotRow) -> OddsSnapshot:
        selections = tuple(
            sorted(
                (
                    OddsSelection(
                        Football1x2Selection(item.selection),
                        Decimal(item.decimal_odds),
                    )
                    for item in row.selections
                    if item.decimal_odds is not None
                ),
                key=lambda item: _SELECTION_ORDER[item.selection],
            )
        )
        return OddsSnapshot(
            id=row.id,
            provider_id=row.provider_id,
            match_id=row.match_id,
            bookmaker=row.bookmaker,
            market=row.market,
            selections=selections,
            collected_at=row.collected_at,
            available_at=row.available_at,
            source=row.source,
            data_mode=row.data_mode,  # type: ignore[arg-type]
            raw_payload_id=row.raw_payload_id,
        )
