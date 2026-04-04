from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.connectors.base import ConnectorBatch, ConnectorRunRequest


class GithubConnector:
    def __init__(
        self,
        *,
        token: str | None = None,
        owner: str | None = None,
        repos: Iterable[str] | None = None,
        per_page: int = 20,
        max_pages: int = 10,
        lookback_minutes: int = 60,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token.strip() if token else None
        self.owner = owner.strip() if owner else None
        self.repos = [repo.strip() for repo in (repos or []) if repo and repo.strip()]
        self.per_page = per_page
        self.max_pages = max(1, max_pages)
        self.lookback_minutes = max(0, lookback_minutes)
        self._client = client or httpx.Client(
            base_url="https://api.github.com",
            timeout=timeout_seconds,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _resolve_targets(self, request: ConnectorRunRequest) -> list[str]:
        component_name = (request.system_component_name or "").strip()
        if component_name:
            if "/" in component_name:
                return [component_name]
            if self.owner:
                return [f"{self.owner}/{component_name}"]
            matched = [
                repo
                for repo in self.repos
                if repo == component_name or repo.endswith(f"/{component_name}")
            ]
            if matched:
                return matched
        return self.repos

    def _request_json(self, path: str, params: dict[str, Any]) -> Any:
        response = self._client.get(path, params=params)
        if response.status_code >= 400:
            snippet = response.text.strip().replace("\n", " ")
            if len(snippet) > 240:
                snippet = snippet[:240] + "..."
            raise RuntimeError(f"{response.status_code} for {path}: {snippet}")
        return response.json()

    def _parse_iso_datetime(self, value: str | None) -> datetime | None:
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

    def _collect_pull_requests(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], datetime | None, bool]:
        items: list[dict[str, Any]] = []
        latest_seen: datetime | None = None
        pagination_limit_hit = False
        for page in range(1, self.max_pages + 1):
            payload = self._request_json(
                f"/repos/{owner}/{repo}/pulls",
                {
                    "state": "all",
                    "per_page": self.per_page,
                    "sort": "updated",
                    "direction": "desc",
                    "page": page,
                },
            )
            if not payload:
                break

            reached_cursor_boundary = False
            for pr in payload:
                updated_at_raw = pr.get("updated_at")
                updated_at = self._parse_iso_datetime(updated_at_raw)
                if updated_at is not None and (
                    latest_seen is None or updated_at > latest_seen
                ):
                    latest_seen = updated_at
                if since is not None and updated_at is not None and updated_at <= since:
                    reached_cursor_boundary = True
                    continue
                items.append(
                    {
                        "kind": "pull_request",
                        "repository": f"{owner}/{repo}",
                        "id": pr.get("id"),
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "url": pr.get("html_url"),
                        "author": (pr.get("user") or {}).get("login"),
                        "updated_at": updated_at_raw,
                        "source_key": f"pull_request:{pr.get('number')}",
                    }
                )

            if since is not None and reached_cursor_boundary:
                break

            if len(payload) < self.per_page:
                break

            if page == self.max_pages:
                pagination_limit_hit = True
                break

        return items, latest_seen, pagination_limit_hit

    def _collect_commits(
        self,
        owner: str,
        repo: str,
        since: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], datetime | None, bool]:
        items: list[dict[str, Any]] = []
        latest_seen: datetime | None = None
        pagination_limit_hit = False
        for page in range(1, self.max_pages + 1):
            payload = self._request_json(
                f"/repos/{owner}/{repo}/commits",
                {"per_page": self.per_page, "page": page},
            )
            if not payload:
                break

            reached_cursor_boundary = False
            for commit in payload:
                commit_block = commit.get("commit") or {}
                commit_author = commit_block.get("author") or {}
                committed_at_raw = commit_author.get("date")
                committed_at = self._parse_iso_datetime(committed_at_raw)
                if committed_at is not None and (
                    latest_seen is None or committed_at > latest_seen
                ):
                    latest_seen = committed_at
                if since is not None and committed_at is not None and committed_at <= since:
                    reached_cursor_boundary = True
                    continue
                items.append(
                    {
                        "kind": "commit",
                        "repository": f"{owner}/{repo}",
                        "id": commit.get("sha"),
                        "sha": commit.get("sha"),
                        "message": commit_block.get("message"),
                        "url": commit.get("html_url"),
                        "author": (commit.get("author") or {}).get("login")
                        or commit_author.get("name"),
                        "committed_at": committed_at_raw,
                        "source_key": f"commit:{commit.get('sha')}",
                    }
                )

            if since is not None and reached_cursor_boundary:
                break

            if len(payload) < self.per_page:
                break

            if page == self.max_pages:
                pagination_limit_hit = True
                break

        return items, latest_seen, pagination_limit_hit

    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch:
        targets = self._resolve_targets(request)
        if not targets:
            raise ValueError(
                "No GitHub repository target configured. Set GITHUB_REPOS or provide owner + system_component_name."
            )

        items: list[dict[str, Any]] = []
        errors: list[str] = []
        warnings: list[str] = []
        latest_cursor_by_target: dict[str, str] = {}
        for target in targets:
            try:
                owner, repo = target.split("/", 1)
                since = self._parse_iso_datetime(request.cursor_by_target.get(target))
                if since is not None and self.lookback_minutes > 0:
                    since = since - timedelta(minutes=self.lookback_minutes)
                pull_items, pull_latest_seen, pull_limit_hit = self._collect_pull_requests(
                    owner, repo, since=since
                )
                commit_items, commit_latest_seen, commit_limit_hit = self._collect_commits(
                    owner, repo, since=since
                )
                items.extend(pull_items)
                items.extend(commit_items)
                if pull_limit_hit:
                    warnings.append(
                        f"{target}: pagination limit hit for pull requests on {target}"
                    )
                if commit_limit_hit:
                    warnings.append(f"{target}: pagination limit hit for commits on {target}")

                latest_seen = pull_latest_seen
                if commit_latest_seen is not None and (
                    latest_seen is None or commit_latest_seen > latest_seen
                ):
                    latest_seen = commit_latest_seen
                if latest_seen is not None:
                    latest_cursor_by_target[target] = latest_seen.isoformat()
            except Exception as exc:
                errors.append(f"{target}: {exc}")

        return ConnectorBatch(
            connector_name="github",
            records_processed=len(items),
            items=items,
            errors=errors,
            warnings=warnings,
            latest_cursor_by_target=latest_cursor_by_target,
        )
