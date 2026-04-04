from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import CodeRepo, Commit, ConnectorRawEvent, PullRequest, SystemComponent
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


def test_create_connector_raw_events_is_resilient_to_stale_duplicate_reads(
    monkeypatch,
) -> None:
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
            }
        ]

        repo.create_connector_raw_events(run1.id, "github", items)

        original_query = repo.db.query

        def stale_query(*entities, **kwargs):
            if (
                len(entities) == 2
                and entities[0] is ConnectorRawEvent.target_key
                and entities[1] is ConnectorRawEvent.source_key
            ):
                class EmptyQuery:
                    def filter(self, *args, **kwargs):
                        return self

                    def all(self):
                        return []

                return EmptyQuery()
            return original_query(*entities, **kwargs)

        monkeypatch.setattr(repo.db, "query", stale_query)

        second_insert = repo.create_connector_raw_events(run2.id, "github", items)

        assert len(second_insert) == 0
        assert repo.db.query(ConnectorRawEvent).count() == 1
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


def test_list_raw_events_by_sync_run_and_connector() -> None:
    repo = build_repo()
    try:
        run = repo.create_sync_run(
            connector_name="github",
            status="running",
            records_processed=0,
            started_at=datetime.now(timezone.utc),
        )
        repo.create_connector_raw_events(
            run.id,
            "github",
            [
                {
                    "kind": "pull_request",
                    "repository": "acme/payment-api",
                    "number": 12,
                    "source_key": "pull_request:12",
                }
            ],
        )

        events = repo.list_connector_raw_events_by_sync_run(run.id, connector_name="github")

        assert len(events) == 1
        assert events[0].connector_name == "github"
        assert events[0].source_key == "pull_request:12"
    finally:
        repo.db.close()


def test_get_code_repo_by_provider_and_repository() -> None:
    repo = build_repo()
    try:
        system_component = SystemComponent(name="payment-api", description="payments")
        repo.db.add(system_component)
        repo.db.commit()
        repo.db.refresh(system_component)

        code_repo = CodeRepo(
            system_component_id=system_component.id,
            provider="github",
            name="claston/micro-cardservice",
            url="https://github.com/claston/micro-cardservice",
            default_branch="main",
        )
        repo.db.add(code_repo)
        repo.db.commit()
        repo.db.refresh(code_repo)

        by_name = repo.get_code_repo_by_provider_and_repository(
            "github", "claston/micro-cardservice"
        )
        by_url = repo.get_code_repo_by_provider_and_repository(
            "github", "claston/micro-cardservice"
        )
        by_slug = repo.get_code_repo_by_provider_and_repository("github", "micro-cardservice")

        assert by_name is not None and by_name.id == code_repo.id
        assert by_url is not None and by_url.id == code_repo.id
        assert by_slug is not None and by_slug.id == code_repo.id
    finally:
        repo.db.close()


def test_update_pull_request_and_commit() -> None:
    repo = build_repo()
    try:
        system_component = SystemComponent(name="payment-api", description="payments")
        repo.db.add(system_component)
        repo.db.commit()
        repo.db.refresh(system_component)

        code_repo = CodeRepo(
            system_component_id=system_component.id,
            provider="github",
            name="payment-api",
            url="https://github.com/acme/payment-api",
            default_branch="main",
        )
        repo.db.add(code_repo)
        repo.db.commit()
        repo.db.refresh(code_repo)

        pull_request = repo.create_pull_request(
            code_repo_id=code_repo.id,
            number="37",
            title="old title",
            status="open",
        )
        commit = repo.create_commit(
            code_repo_id=code_repo.id,
            sha="abc123",
            message="old message",
        )

        updated_pull_request = repo.update_pull_request(
            pull_request.id,
            code_repo_id=code_repo.id,
            number="37",
            title="new title",
            status="closed",
        )
        updated_commit = repo.update_commit(
            commit.id,
            code_repo_id=code_repo.id,
            sha="abc123",
            message="new message",
        )

        fetched_pull_request = repo.get_pull_request_by_repo_and_number(code_repo.id, "37")
        fetched_commit = repo.get_commit_by_repo_and_sha(code_repo.id, "abc123")

        assert isinstance(updated_pull_request, PullRequest)
        assert isinstance(updated_commit, Commit)
        assert fetched_pull_request is not None
        assert fetched_pull_request.title == "new title"
        assert fetched_commit is not None
        assert fetched_commit.message == "new message"
    finally:
        repo.db.close()
