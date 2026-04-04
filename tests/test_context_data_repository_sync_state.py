from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ConnectorRawEvent
from app.repositories.system_component_repository import SqlAlchemyContextDataRepository


def build_repo() -> SqlAlchemyContextDataRepository:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session_local()
    return SqlAlchemyContextDataRepository(db)


def test_create_connector_raw_events_is_idempotent_by_source_key() -> None:
    repo = build_repo()
    try:
        run1 = repo.create_sync_run(
            connector_name="github",
            status="running",
            records_processed=0,
            started_at=datetime.now(timezone.utc),
        )
        run2 = repo.create_sync_run(
            connector_name="github",
            status="running",
            records_processed=0,
            started_at=datetime.now(timezone.utc),
        )
        items = [
            {
                "kind": "pull_request",
                "repository": "acme/payment-api",
                "number": 12,
                "source_key": "pull_request:12",
            },
            {
                "kind": "commit",
                "repository": "acme/payment-api",
                "sha": "abc123",
                "source_key": "commit:abc123",
            },
        ]

        first_insert = repo.create_connector_raw_events(run1.id, "github", items)
        second_insert = repo.create_connector_raw_events(run2.id, "github", items)

        assert len(first_insert) == 2
        assert len(second_insert) == 0
        assert repo.db.query(ConnectorRawEvent).count() == 2
    finally:
        repo.db.close()


def test_sync_cursor_state_round_trip() -> None:
    repo = build_repo()
    try:
        assert repo.get_connector_sync_cursors("github") == {}

        repo.upsert_connector_sync_cursors(
            "github",
            {
                "acme/payment-api": "2026-04-03T12:00:00+00:00",
                "acme/ledger-api": "2026-04-03T12:05:00+00:00",
            },
        )

        assert repo.get_connector_sync_cursors("github") == {
            "acme/payment-api": "2026-04-03T12:00:00+00:00",
            "acme/ledger-api": "2026-04-03T12:05:00+00:00",
        }

        repo.upsert_connector_sync_cursors(
            "github",
            {"acme/payment-api": "2026-04-03T12:10:00+00:00"},
        )

        assert repo.get_connector_sync_cursors("github")["acme/payment-api"] == (
            "2026-04-03T12:10:00+00:00"
        )
    finally:
        repo.db.close()
