import hashlib
import json
from datetime import datetime, timezone
from typing import List, Protocol
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    ApiContract,
    CodeRepo,
    Commit,
    ConnectorRawEvent,
    ConnectorSyncState,
    Dependency,
    Deployment,
    Endpoint,
    PullRequest,
    RuntimeSnapshot,
    SyncRun,
    SystemComponent,
)


class DuplicateContextEntityError(Exception):
    pass


class ContextEntityReferenceNotFoundError(Exception):
    pass


class ContextEntityRepository(Protocol):
    def create_pull_request(self, **kwargs) -> PullRequest: ...

    def list_pull_requests(self) -> List[PullRequest]: ...

    def create_commit(self, **kwargs) -> Commit: ...

    def list_commits(self) -> List[Commit]: ...

    def create_deployment(self, **kwargs) -> Deployment: ...

    def list_deployments(self) -> List[Deployment]: ...

    def create_runtime_snapshot(self, **kwargs) -> RuntimeSnapshot: ...

    def list_runtime_snapshots(self) -> List[RuntimeSnapshot]: ...

    def create_api_contract(self, **kwargs) -> ApiContract: ...

    def list_api_contracts(self) -> List[ApiContract]: ...

    def create_endpoint(self, **kwargs) -> Endpoint: ...

    def list_endpoints(self) -> List[Endpoint]: ...

    def create_dependency(self, **kwargs) -> Dependency: ...

    def list_dependencies(self) -> List[Dependency]: ...


class SyncRepository(Protocol):
    def create_sync_run(self, **kwargs) -> SyncRun: ...

    def list_sync_runs(self) -> List[SyncRun]: ...

    def list_sync_runs_by_status(self, status: str) -> List[SyncRun]: ...

    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None: ...

    def update_sync_run(self, sync_run_id: UUID, **kwargs) -> SyncRun: ...

    def create_connector_raw_events(
        self, sync_run_id: UUID, connector_name: str, items: list[dict]
    ) -> List[ConnectorRawEvent]: ...

    def get_connector_sync_cursors(self, connector_name: str) -> dict[str, str]: ...

    def upsert_connector_sync_cursors(
        self, connector_name: str, cursor_by_target: dict[str, str]
    ) -> None: ...

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ) -> List[ConnectorRawEvent]: ...


class GithubNormalizationRepository(Protocol):
    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None: ...

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ) -> List[ConnectorRawEvent]: ...

    def get_code_repo_by_provider_and_repository(
        self, provider: str, repository: str
    ) -> CodeRepo | None: ...

    def get_pull_request_by_repo_and_number(
        self, code_repo_id: UUID, number: str
    ) -> PullRequest | None: ...

    def create_pull_request(self, **kwargs) -> PullRequest: ...

    def update_pull_request(self, pull_request_id: UUID, **kwargs) -> PullRequest: ...

    def get_commit_by_repo_and_sha(
        self, code_repo_id: UUID, sha: str
    ) -> Commit | None: ...

    def create_commit(self, **kwargs) -> Commit: ...

    def update_commit(self, commit_id: UUID, **kwargs) -> Commit: ...


class RenderRuntimeNormalizationRepository(Protocol):
    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None: ...

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ) -> List[ConnectorRawEvent]: ...

    def get_system_component_by_name(
        self, system_component_name: str
    ) -> SystemComponent | None: ...

    def get_runtime_snapshot_by_component_environment_and_captured_at(
        self,
        system_component_id: UUID,
        environment: str,
        captured_at: datetime,
    ) -> RuntimeSnapshot | None: ...

    def create_runtime_snapshot(self, **kwargs) -> RuntimeSnapshot: ...

    def update_runtime_snapshot(
        self, runtime_snapshot_id: UUID, **kwargs
    ) -> RuntimeSnapshot: ...


class ContextQueryRepository(Protocol):
    def list_system_component_names(self) -> List[str]: ...

    def list_known_environments(self) -> List[str]: ...

    def count_system_components(self) -> int: ...

    def count_code_repos(self) -> int: ...

    def count_deployments(self) -> int: ...

    def count_runtime_snapshots(self) -> int: ...

    def get_system_component_by_name(
        self, system_component_name: str
    ) -> SystemComponent | None: ...

    def get_latest_deployment_for_system_component(
        self, system_component_id: UUID, environment: str | None = None
    ) -> Deployment | None: ...

    def get_latest_runtime_for_system_component(
        self, system_component_id: UUID, environment: str | None = None
    ) -> RuntimeSnapshot | None: ...

    def get_recent_pull_requests_count_for_system_component(
        self, system_component_id: UUID
    ) -> int: ...

    def get_recent_commits_count_for_system_component(self, system_component_id: UUID) -> int: ...

    def get_dependencies_for_system_component(
        self, system_component_id: UUID
    ) -> List[Dependency]: ...


class _SqlAlchemyContextRepositoryBase:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _create(self, model_class, **kwargs):
        instance = model_class(**kwargs)
        try:
            self.db.add(instance)
            self.db.commit()
            self.db.refresh(instance)
            return instance
        except IntegrityError as exc:
            self.db.rollback()
            orig = exc.orig
            pgcode = getattr(orig, "pgcode", None)
            message = str(orig)
            is_unique_violation = pgcode == "23505" or "UNIQUE constraint failed" in message
            is_foreign_key_violation = (
                pgcode == "23503" or "FOREIGN KEY constraint failed" in message
            )
            if is_unique_violation:
                raise DuplicateContextEntityError from exc
            if is_foreign_key_violation:
                raise ContextEntityReferenceNotFoundError from exc
            raise

    def _resolve_event_identity(self, item: dict) -> tuple[str, str]:
        target_key = str(item.get("target_key") or item.get("repository") or "__global__")

        explicit_source = item.get("source_key")
        if explicit_source:
            return target_key, str(explicit_source)

        kind = str(item.get("kind") or "item")
        intrinsic = item.get("id") or item.get("number") or item.get("sha")
        if intrinsic is not None:
            return target_key, f"{kind}:{intrinsic}"

        canonical_payload = json.dumps(
            item,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
        return target_key, f"{kind}:sha256:{payload_hash}"

    def _parse_cursor_datetime(self, value: str) -> datetime | None:
        if not value:
            return None
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _is_cursor_newer(self, candidate: str, current: str) -> bool:
        candidate_dt = self._parse_cursor_datetime(candidate)
        current_dt = self._parse_cursor_datetime(current)
        if candidate_dt is None or current_dt is None:
            return candidate != current
        return candidate_dt > current_dt


class SqlAlchemyContextEntityRepository(_SqlAlchemyContextRepositoryBase):
    def create_pull_request(self, **kwargs) -> PullRequest:
        return self._create(PullRequest, **kwargs)

    def list_pull_requests(self) -> List[PullRequest]:
        return self.db.query(PullRequest).all()

    def create_commit(self, **kwargs) -> Commit:
        return self._create(Commit, **kwargs)

    def list_commits(self) -> List[Commit]:
        return self.db.query(Commit).all()

    def create_deployment(self, **kwargs) -> Deployment:
        return self._create(Deployment, **kwargs)

    def list_deployments(self) -> List[Deployment]:
        return self.db.query(Deployment).all()

    def create_runtime_snapshot(self, **kwargs) -> RuntimeSnapshot:
        return self._create(RuntimeSnapshot, **kwargs)

    def list_runtime_snapshots(self) -> List[RuntimeSnapshot]:
        return self.db.query(RuntimeSnapshot).all()

    def create_api_contract(self, **kwargs) -> ApiContract:
        return self._create(ApiContract, **kwargs)

    def list_api_contracts(self) -> List[ApiContract]:
        return self.db.query(ApiContract).all()

    def create_endpoint(self, **kwargs) -> Endpoint:
        return self._create(Endpoint, **kwargs)

    def list_endpoints(self) -> List[Endpoint]:
        return self.db.query(Endpoint).all()

    def create_dependency(self, **kwargs) -> Dependency:
        return self._create(Dependency, **kwargs)

    def list_dependencies(self) -> List[Dependency]:
        return self.db.query(Dependency).all()


class SqlAlchemySyncRepository(_SqlAlchemyContextRepositoryBase):
    def create_sync_run(self, **kwargs) -> SyncRun:
        return self._create(SyncRun, **kwargs)

    def list_sync_runs(self) -> List[SyncRun]:
        return self.db.query(SyncRun).all()

    def list_sync_runs_by_status(self, status: str) -> List[SyncRun]:
        return self.db.query(SyncRun).filter(SyncRun.status == status).all()

    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None:
        return self.db.query(SyncRun).filter(SyncRun.id == sync_run_id).first()

    def update_sync_run(self, sync_run_id: UUID, **kwargs) -> SyncRun:
        item = self.get_sync_run_by_id(sync_run_id)
        if item is None:
            raise ContextEntityReferenceNotFoundError
        for key, value in kwargs.items():
            setattr(item, key, value)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def create_connector_raw_events(
        self, sync_run_id: UUID, connector_name: str, items: list[dict]
    ) -> List[ConnectorRawEvent]:
        if not items:
            return []

        resolved_items: list[tuple[str, str, dict]] = []
        for item in items:
            target_key, source_key = self._resolve_event_identity(item)
            resolved_items.append((target_key, source_key, item))

        seen_batch: set[tuple[str, str]] = set()
        unique_items: list[tuple[str, str, dict]] = []
        for target_key, source_key, item in resolved_items:
            key = (target_key, source_key)
            if key in seen_batch:
                continue
            seen_batch.add(key)
            unique_items.append((target_key, source_key, item))

        now = datetime.now(timezone.utc)
        rows_to_insert = []
        candidate_ids: list[UUID] = []
        for target_key, source_key, item in unique_items:
            event_id = uuid4()
            candidate_ids.append(event_id)
            rows_to_insert.append(
                {
                    "id": event_id,
                    "sync_run_id": sync_run_id,
                    "connector_name": connector_name,
                    "target_key": target_key,
                    "source_key": source_key,
                    "payload": item,
                    "collected_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
            )

        dialect_name = self.db.bind.dialect.name if self.db.bind is not None else None
        if dialect_name == "postgresql":
            statement = postgresql_insert(ConnectorRawEvent).values(rows_to_insert)
            statement = statement.on_conflict_do_nothing(
                constraint="connector_raw_event_identity_key"
            )
        elif dialect_name == "sqlite":
            statement = sqlite_insert(ConnectorRawEvent).values(rows_to_insert)
            statement = statement.on_conflict_do_nothing(
                index_elements=["connector_name", "target_key", "source_key"]
            )
        else:
            raise RuntimeError(
                f"unsupported database dialect for atomic raw-event insert: {dialect_name}"
            )

        self.db.execute(statement)
        self.db.commit()

        inserted_events = (
            self.db.query(ConnectorRawEvent)
            .filter(ConnectorRawEvent.id.in_(candidate_ids))
            .all()
        )
        if not inserted_events:
            return []

        event_by_id = {event.id: event for event in inserted_events}
        return [event_by_id[event_id] for event_id in candidate_ids if event_id in event_by_id]

    def get_connector_sync_cursors(self, connector_name: str) -> dict[str, str]:
        states = (
            self.db.query(ConnectorSyncState)
            .filter(ConnectorSyncState.connector_name == connector_name)
            .all()
        )
        return {state.target_key: state.last_cursor for state in states}

    def upsert_connector_sync_cursors(
        self, connector_name: str, cursor_by_target: dict[str, str]
    ) -> None:
        if not cursor_by_target:
            return

        for target_key, last_cursor in cursor_by_target.items():
            state = (
                self.db.query(ConnectorSyncState)
                .filter(
                    ConnectorSyncState.connector_name == connector_name,
                    ConnectorSyncState.target_key == target_key,
                )
                .first()
            )
            if state is None:
                state = ConnectorSyncState(
                    connector_name=connector_name,
                    target_key=target_key,
                    last_cursor=last_cursor,
                )
                self.db.add(state)
                continue
            if self._is_cursor_newer(last_cursor, state.last_cursor):
                state.last_cursor = last_cursor
                self.db.add(state)

        self.db.commit()

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ) -> List[ConnectorRawEvent]:
        query = self.db.query(ConnectorRawEvent).filter(
            ConnectorRawEvent.sync_run_id == sync_run_id
        )
        if connector_name:
            query = query.filter(ConnectorRawEvent.connector_name == connector_name)
        return query.order_by(
            ConnectorRawEvent.created_at.asc(), ConnectorRawEvent.id.asc()
        ).all()


class SqlAlchemyGithubNormalizationRepository(_SqlAlchemyContextRepositoryBase):
    def get_sync_run_by_id(self, sync_run_id: UUID) -> SyncRun | None:
        return self.db.query(SyncRun).filter(SyncRun.id == sync_run_id).first()

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ) -> List[ConnectorRawEvent]:
        query = self.db.query(ConnectorRawEvent).filter(
            ConnectorRawEvent.sync_run_id == sync_run_id
        )
        if connector_name:
            query = query.filter(ConnectorRawEvent.connector_name == connector_name)
        return query.order_by(
            ConnectorRawEvent.created_at.asc(), ConnectorRawEvent.id.asc()
        ).all()

    def get_code_repo_by_provider_and_repository(
        self, provider: str, repository: str
    ) -> CodeRepo | None:
        normalized_repository = repository.strip().strip("/")
        if not normalized_repository:
            return None

        exact_name_match = (
            self.db.query(CodeRepo)
            .filter(
                CodeRepo.provider == provider,
                CodeRepo.name == normalized_repository,
            )
            .first()
        )
        if exact_name_match is not None:
            return exact_name_match

        url_match = (
            self.db.query(CodeRepo)
            .filter(
                CodeRepo.provider == provider,
                (
                    CodeRepo.url.ilike(f"%/{normalized_repository}")
                    | CodeRepo.url.ilike(f"%/{normalized_repository}.git")
                ),
            )
            .first()
        )
        if url_match is not None:
            return url_match

        slug = normalized_repository.split("/")[-1]
        slug_matches = (
            self.db.query(CodeRepo)
            .filter(
                CodeRepo.provider == provider,
                CodeRepo.name == slug,
            )
            .all()
        )
        if len(slug_matches) == 1:
            return slug_matches[0]
        return None

    def get_pull_request_by_repo_and_number(
        self, code_repo_id: UUID, number: str
    ) -> PullRequest | None:
        return (
            self.db.query(PullRequest)
            .filter(
                PullRequest.code_repo_id == code_repo_id,
                PullRequest.number == number,
            )
            .first()
        )

    def create_pull_request(self, **kwargs) -> PullRequest:
        return self._create(PullRequest, **kwargs)

    def update_pull_request(self, pull_request_id: UUID, **kwargs) -> PullRequest:
        pull_request = (
            self.db.query(PullRequest).filter(PullRequest.id == pull_request_id).first()
        )
        if pull_request is None:
            raise ContextEntityReferenceNotFoundError
        for key, value in kwargs.items():
            setattr(pull_request, key, value)
        self.db.add(pull_request)
        self.db.commit()
        self.db.refresh(pull_request)
        return pull_request

    def get_commit_by_repo_and_sha(
        self, code_repo_id: UUID, sha: str
    ) -> Commit | None:
        return (
            self.db.query(Commit)
            .filter(
                Commit.code_repo_id == code_repo_id,
                Commit.sha == sha,
            )
            .first()
        )

    def create_commit(self, **kwargs) -> Commit:
        return self._create(Commit, **kwargs)

    def update_commit(self, commit_id: UUID, **kwargs) -> Commit:
        commit = self.db.query(Commit).filter(Commit.id == commit_id).first()
        if commit is None:
            raise ContextEntityReferenceNotFoundError
        for key, value in kwargs.items():
            setattr(commit, key, value)
        self.db.add(commit)
        self.db.commit()
        self.db.refresh(commit)
        return commit

    def get_system_component_by_name(
        self, system_component_name: str
    ) -> SystemComponent | None:
        return (
            self.db.query(SystemComponent)
            .filter(SystemComponent.name == system_component_name)
            .first()
        )

    def get_runtime_snapshot_by_component_environment_and_captured_at(
        self,
        system_component_id: UUID,
        environment: str,
        captured_at: datetime,
    ) -> RuntimeSnapshot | None:
        return (
            self.db.query(RuntimeSnapshot)
            .filter(
                RuntimeSnapshot.system_component_id == system_component_id,
                RuntimeSnapshot.environment == environment,
                RuntimeSnapshot.captured_at == captured_at,
            )
            .first()
        )

    def create_runtime_snapshot(self, **kwargs) -> RuntimeSnapshot:
        return self._create(RuntimeSnapshot, **kwargs)

    def update_runtime_snapshot(
        self, runtime_snapshot_id: UUID, **kwargs
    ) -> RuntimeSnapshot:
        snapshot = (
            self.db.query(RuntimeSnapshot)
            .filter(RuntimeSnapshot.id == runtime_snapshot_id)
            .first()
        )
        if snapshot is None:
            raise ContextEntityReferenceNotFoundError
        for key, value in kwargs.items():
            setattr(snapshot, key, value)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot


class SqlAlchemyContextQueryRepository(_SqlAlchemyContextRepositoryBase):
    def list_system_component_names(self) -> List[str]:
        rows = (
            self.db.query(SystemComponent.name)
            .order_by(SystemComponent.name.asc())
            .all()
        )
        return [name for (name,) in rows if name]

    def list_known_environments(self) -> List[str]:
        deployment_rows = self.db.query(Deployment.environment).distinct().all()
        runtime_rows = self.db.query(RuntimeSnapshot.environment).distinct().all()
        known = {
            value.strip()
            for (value,) in deployment_rows + runtime_rows
            if isinstance(value, str) and value.strip()
        }
        return sorted(known)

    def count_system_components(self) -> int:
        return self.db.query(SystemComponent).count()

    def count_code_repos(self) -> int:
        return self.db.query(CodeRepo).count()

    def count_deployments(self) -> int:
        return self.db.query(Deployment).count()

    def count_runtime_snapshots(self) -> int:
        return self.db.query(RuntimeSnapshot).count()

    def get_system_component_by_name(self, system_component_name: str) -> SystemComponent | None:
        return (
            self.db.query(SystemComponent)
            .filter(SystemComponent.name == system_component_name)
            .first()
        )

    def get_latest_deployment_for_system_component(
        self, system_component_id: UUID, environment: str | None = None
    ) -> Deployment | None:
        query = self.db.query(Deployment).filter(
            Deployment.system_component_id == system_component_id
        )
        if environment:
            query = query.filter(Deployment.environment == environment)
        return query.order_by(Deployment.deployed_at.desc()).first()

    def get_latest_runtime_for_system_component(
        self, system_component_id: UUID, environment: str | None = None
    ) -> RuntimeSnapshot | None:
        query = self.db.query(RuntimeSnapshot).filter(
            RuntimeSnapshot.system_component_id == system_component_id
        )
        if environment:
            query = query.filter(RuntimeSnapshot.environment == environment)
        return query.order_by(RuntimeSnapshot.captured_at.desc()).first()

    def get_recent_pull_requests_count_for_system_component(
        self, system_component_id: UUID
    ) -> int:
        return (
            self.db.query(PullRequest)
            .join(CodeRepo, PullRequest.code_repo_id == CodeRepo.id)
            .filter(CodeRepo.system_component_id == system_component_id)
            .count()
        )

    def get_recent_commits_count_for_system_component(self, system_component_id: UUID) -> int:
        return (
            self.db.query(Commit)
            .join(CodeRepo, Commit.code_repo_id == CodeRepo.id)
            .filter(CodeRepo.system_component_id == system_component_id)
            .count()
        )

    def get_dependencies_for_system_component(self, system_component_id: UUID) -> List[Dependency]:
        return (
            self.db.query(Dependency)
            .filter(Dependency.source_system_component_id == system_component_id)
            .all()
        )
