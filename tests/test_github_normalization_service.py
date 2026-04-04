from uuid import UUID, uuid4

from app.application.github_normalization_service import (
    GithubNormalizationService,
    NormalizationSyncRunNotFoundError,
    UnsupportedNormalizationConnectorError,
)


class FakeContextRepository:
    def __init__(self) -> None:
        self.sync_runs: dict[UUID, dict] = {}
        self.raw_events_by_sync_run: dict[UUID, list[dict]] = {}
        self.code_repos_by_repository: dict[str, dict] = {}
        self.pull_requests: dict[tuple[UUID, str], dict] = {}
        self.commits: dict[tuple[UUID, str], dict] = {}

    def get_sync_run_by_id(self, sync_run_id: UUID):
        return self.sync_runs.get(sync_run_id)

    def list_connector_raw_events_by_sync_run(
        self, sync_run_id: UUID, connector_name: str | None = None
    ):
        events = self.raw_events_by_sync_run.get(sync_run_id, [])
        if connector_name is None:
            return events
        return [event for event in events if event.get("connector_name") == connector_name]

    def get_code_repo_by_provider_and_repository(self, provider: str, repository: str):
        if provider != "github":
            return None
        return self.code_repos_by_repository.get(repository)

    def get_pull_request_by_repo_and_number(self, code_repo_id: UUID, number: str):
        return self.pull_requests.get((code_repo_id, number))

    def create_pull_request(self, **kwargs):
        item = {"id": uuid4(), **kwargs}
        self.pull_requests[(kwargs["code_repo_id"], kwargs["number"])] = item
        return item

    def update_pull_request(self, pull_request_id: UUID, **kwargs):
        key = (kwargs["code_repo_id"], kwargs["number"])
        current = self.pull_requests[key]
        current.update(kwargs)
        return current

    def get_commit_by_repo_and_sha(self, code_repo_id: UUID, sha: str):
        return self.commits.get((code_repo_id, sha))

    def create_commit(self, **kwargs):
        item = {"id": uuid4(), **kwargs}
        self.commits[(kwargs["code_repo_id"], kwargs["sha"])] = item
        return item

    def update_commit(self, commit_id: UUID, **kwargs):
        key = (kwargs["code_repo_id"], kwargs["sha"])
        current = self.commits[key]
        current.update(kwargs)
        return current


def test_normalize_sync_run_creates_pull_request_and_commit() -> None:
    repo = FakeContextRepository()
    service = GithubNormalizationService(repo)
    sync_run_id = uuid4()
    code_repo_id = uuid4()
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "github"}
    repo.code_repos_by_repository["claston/micro-cardservice"] = {
        "id": code_repo_id,
        "provider": "github",
        "name": "claston/micro-cardservice",
    }
    repo.raw_events_by_sync_run[sync_run_id] = [
        {
            "id": uuid4(),
            "connector_name": "github",
            "payload": {
                "kind": "pull_request",
                "repository": "claston/micro-cardservice",
                "number": 37,
                "title": "docs: add marker",
                "state": "open",
                "author": "alice",
                "url": "https://github.com/claston/micro-cardservice/pull/37",
            },
        },
        {
            "id": uuid4(),
            "connector_name": "github",
            "payload": {
                "kind": "commit",
                "repository": "claston/micro-cardservice",
                "sha": "f7079671bd93e410ff7270f9ac15b6cdd508f8a9",
                "message": "docs(readme): add sync marker",
                "author": "alice",
                "committed_at": "2026-04-03T23:53:28Z",
            },
        },
    ]

    summary = service.normalize_sync_run(sync_run_id)

    assert summary["raw_events_read"] == 2
    assert summary["pull_requests_created"] == 1
    assert summary["commits_created"] == 1
    assert summary["pull_requests_updated"] == 0
    assert summary["commits_updated"] == 0
    assert summary["skipped"] == 0
    assert summary["errors"] == []
    assert (code_repo_id, "37") in repo.pull_requests
    assert (
        code_repo_id,
        "f7079671bd93e410ff7270f9ac15b6cdd508f8a9",
    ) in repo.commits


def test_normalize_sync_run_updates_existing_entities() -> None:
    repo = FakeContextRepository()
    service = GithubNormalizationService(repo)
    sync_run_id = uuid4()
    code_repo_id = uuid4()
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "github"}
    repo.code_repos_by_repository["claston/micro-cardservice"] = {"id": code_repo_id}
    repo.pull_requests[(code_repo_id, "37")] = {
        "id": uuid4(),
        "code_repo_id": code_repo_id,
        "number": "37",
        "title": "old",
        "status": "open",
    }
    repo.commits[(code_repo_id, "f707")] = {
        "id": uuid4(),
        "code_repo_id": code_repo_id,
        "sha": "f707",
        "message": "old",
    }
    repo.raw_events_by_sync_run[sync_run_id] = [
        {
            "id": uuid4(),
            "connector_name": "github",
            "payload": {
                "kind": "pull_request",
                "repository": "claston/micro-cardservice",
                "number": "37",
                "title": "new title",
                "state": "closed",
                "merged_at": "2026-04-04T00:00:00Z",
            },
        },
        {
            "id": uuid4(),
            "connector_name": "github",
            "payload": {
                "kind": "commit",
                "repository": "claston/micro-cardservice",
                "sha": "f707",
                "message": "new message",
            },
        },
    ]

    summary = service.normalize_sync_run(sync_run_id)

    assert summary["pull_requests_created"] == 0
    assert summary["commits_created"] == 0
    assert summary["pull_requests_updated"] == 1
    assert summary["commits_updated"] == 1
    assert repo.pull_requests[(code_repo_id, "37")]["status"] == "merged"
    assert repo.commits[(code_repo_id, "f707")]["message"] == "new message"


def test_normalize_sync_run_raises_when_sync_run_missing() -> None:
    repo = FakeContextRepository()
    service = GithubNormalizationService(repo)

    try:
        service.normalize_sync_run(uuid4())
    except NormalizationSyncRunNotFoundError:
        assert True
    else:
        raise AssertionError("expected NormalizationSyncRunNotFoundError")


def test_normalize_sync_run_raises_when_connector_is_not_github() -> None:
    repo = FakeContextRepository()
    service = GithubNormalizationService(repo)
    sync_run_id = uuid4()
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "runtime"}

    try:
        service.normalize_sync_run(sync_run_id)
    except UnsupportedNormalizationConnectorError:
        assert True
    else:
        raise AssertionError("expected UnsupportedNormalizationConnectorError")


def test_normalize_sync_run_skips_when_code_repo_not_found() -> None:
    repo = FakeContextRepository()
    service = GithubNormalizationService(repo)
    sync_run_id = uuid4()
    repo.sync_runs[sync_run_id] = {"id": sync_run_id, "connector_name": "github"}
    repo.raw_events_by_sync_run[sync_run_id] = [
        {
            "id": uuid4(),
            "connector_name": "github",
            "payload": {
                "kind": "pull_request",
                "repository": "claston/micro-cardservice",
                "number": 37,
                "title": "missing repo",
                "state": "open",
            },
        }
    ]

    summary = service.normalize_sync_run(sync_run_id)

    assert summary["raw_events_read"] == 1
    assert summary["skipped"] == 1
    assert summary["pull_requests_created"] == 0
    assert "code repo not found" in summary["errors"][0]
