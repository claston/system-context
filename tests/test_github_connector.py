import json

import httpx

from app.connectors import GithubConnector
from app.connectors.base import ConnectorRunRequest


def build_mock_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(base_url="https://api.github.com", transport=transport, timeout=5.0)


def test_collect_reads_pulls_and_commits_for_configured_repo() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/payment-api/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 101,
                        "number": 12,
                        "title": "feat: add checkout",
                        "state": "open",
                        "html_url": "https://github.com/acme/payment-api/pull/12",
                        "updated_at": "2026-04-03T12:00:00Z",
                        "user": {"login": "alice"},
                    }
                ],
            )
        if request.url.path == "/repos/acme/payment-api/commits":
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "abc123",
                        "html_url": "https://github.com/acme/payment-api/commit/abc123",
                        "commit": {
                            "message": "fix: timeout",
                            "author": {"name": "bob", "date": "2026-04-03T12:01:00Z"},
                        },
                        "author": {"login": "bob"},
                    }
                ],
            )
        return httpx.Response(404, json={"message": "not found"})

    client = build_mock_client(handler)
    connector = GithubConnector(client=client, repos=["acme/payment-api"])

    batch = connector.collect(ConnectorRunRequest())

    assert batch.connector_name == "github"
    assert batch.records_processed == 2
    assert len(batch.items) == 2
    assert batch.errors == []
    assert batch.items[0]["kind"] == "pull_request"
    assert batch.items[1]["kind"] == "commit"
    assert batch.items[0]["repository"] == "acme/payment-api"


def test_collect_uses_owner_plus_component_name_when_request_provided() -> None:
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        if request.url.path.endswith("/pulls"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/commits"):
            return httpx.Response(200, json=[])
        return httpx.Response(404, json={"message": "not found"})

    client = build_mock_client(handler)
    connector = GithubConnector(client=client, owner="acme")

    batch = connector.collect(ConnectorRunRequest(system_component_name="ledger-api"))

    assert batch.records_processed == 0
    assert "/repos/acme/ledger-api/pulls" in requested_paths
    assert "/repos/acme/ledger-api/commits" in requested_paths


def test_collect_reports_errors_and_continues_other_repositories() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/repos/acme/broken-api/"):
            return httpx.Response(500, text=json.dumps({"message": "boom"}))
        if request.url.path == "/repos/acme/ok-api/pulls":
            return httpx.Response(200, json=[])
        if request.url.path == "/repos/acme/ok-api/commits":
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "def456",
                        "html_url": "https://github.com/acme/ok-api/commit/def456",
                        "commit": {
                            "message": "chore: update deps",
                            "author": {"name": "carol", "date": "2026-04-03T12:02:00Z"},
                        },
                        "author": {"login": "carol"},
                    }
                ],
            )
        return httpx.Response(404, json={"message": "not found"})

    client = build_mock_client(handler)
    connector = GithubConnector(client=client, repos=["acme/broken-api", "acme/ok-api"])

    batch = connector.collect(ConnectorRunRequest())

    assert batch.records_processed == 1
    assert len(batch.items) == 1
    assert len(batch.errors) == 1
    assert "broken-api" in batch.errors[0]


def test_collect_requires_target_repository() -> None:
    connector = GithubConnector(repos=[])

    try:
        connector.collect(ConnectorRunRequest())
    except ValueError as exc:
        assert "No GitHub repository target configured" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_collect_filters_items_using_cursor_and_returns_latest_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/payment-api/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 101,
                        "number": 12,
                        "title": "feat: old",
                        "state": "open",
                        "html_url": "https://github.com/acme/payment-api/pull/12",
                        "updated_at": "2026-04-03T12:00:00Z",
                        "user": {"login": "alice"},
                    },
                    {
                        "id": 102,
                        "number": 13,
                        "title": "feat: new",
                        "state": "open",
                        "html_url": "https://github.com/acme/payment-api/pull/13",
                        "updated_at": "2026-04-03T12:01:00Z",
                        "user": {"login": "alice"},
                    },
                ],
            )
        if request.url.path == "/repos/acme/payment-api/commits":
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "old1",
                        "html_url": "https://github.com/acme/payment-api/commit/old1",
                        "commit": {
                            "message": "fix: old",
                            "author": {"name": "bob", "date": "2026-04-03T12:00:10Z"},
                        },
                        "author": {"login": "bob"},
                    },
                    {
                        "sha": "new1",
                        "html_url": "https://github.com/acme/payment-api/commit/new1",
                        "commit": {
                            "message": "fix: new",
                            "author": {"name": "bob", "date": "2026-04-03T12:02:00Z"},
                        },
                        "author": {"login": "bob"},
                    },
                ],
            )
        return httpx.Response(404, json={"message": "not found"})

    client = build_mock_client(handler)
    connector = GithubConnector(client=client, repos=["acme/payment-api"], lookback_minutes=0)

    batch = connector.collect(
        ConnectorRunRequest(
            cursor_by_target={"acme/payment-api": "2026-04-03T12:00:30Z"}
        )
    )

    assert batch.records_processed == 2
    assert [item["id"] for item in batch.items] == [102, "new1"]
    assert (
        batch.latest_cursor_by_target["acme/payment-api"] == "2026-04-03T12:02:00+00:00"
    )


def test_collect_with_lookback_includes_out_of_order_commit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/acme/payment-api/pulls":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 200,
                        "number": 37,
                        "title": "docs: sync marker",
                        "state": "closed",
                        "html_url": "https://github.com/acme/payment-api/pull/37",
                        "updated_at": "2026-04-03T23:58:54Z",
                        "user": {"login": "alice"},
                    }
                ],
            )
        if request.url.path == "/repos/acme/payment-api/commits":
            return httpx.Response(
                200,
                json=[
                    {
                        "sha": "f7079671bd93e410ff7270f9ac15b6cdd508f8a9",
                        "html_url": "https://github.com/acme/payment-api/commit/f7079671bd93e410ff7270f9ac15b6cdd508f8a9",
                        "commit": {
                            "message": "docs(readme): add sync marker",
                            "author": {"name": "bob", "date": "2026-04-03T23:53:28Z"},
                        },
                        "author": {"login": "bob"},
                    }
                ],
            )
        return httpx.Response(404, json={"message": "not found"})

    client = build_mock_client(handler)
    connector = GithubConnector(client=client, repos=["acme/payment-api"], lookback_minutes=60)

    batch = connector.collect(
        ConnectorRunRequest(
            cursor_by_target={"acme/payment-api": "2026-04-03T23:58:54Z"}
        )
    )

    assert batch.records_processed == 2
    assert "commit:f7079671bd93e410ff7270f9ac15b6cdd508f8a9" in {
        item["source_key"] for item in batch.items
    }
