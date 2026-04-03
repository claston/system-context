from __future__ import annotations

from collections.abc import Iterable
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
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token.strip() if token else None
        self.owner = owner.strip() if owner else None
        self.repos = [repo.strip() for repo in (repos or []) if repo and repo.strip()]
        self.per_page = per_page
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

    def _collect_pull_requests(self, owner: str, repo: str) -> list[dict[str, Any]]:
        payload = self._request_json(
            f"/repos/{owner}/{repo}/pulls",
            {"state": "all", "per_page": self.per_page, "sort": "updated", "direction": "desc"},
        )
        items: list[dict[str, Any]] = []
        for pr in payload:
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
                    "updated_at": pr.get("updated_at"),
                }
            )
        return items

    def _collect_commits(self, owner: str, repo: str) -> list[dict[str, Any]]:
        payload = self._request_json(
            f"/repos/{owner}/{repo}/commits",
            {"per_page": self.per_page},
        )
        items: list[dict[str, Any]] = []
        for commit in payload:
            commit_block = commit.get("commit") or {}
            commit_author = commit_block.get("author") or {}
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
                    "committed_at": commit_author.get("date"),
                }
            )
        return items

    def collect(self, request: ConnectorRunRequest) -> ConnectorBatch:
        targets = self._resolve_targets(request)
        if not targets:
            raise ValueError(
                "No GitHub repository target configured. Set GITHUB_REPOS or provide owner + system_component_name."
            )

        items: list[dict[str, Any]] = []
        errors: list[str] = []
        for target in targets:
            try:
                owner, repo = target.split("/", 1)
                items.extend(self._collect_pull_requests(owner, repo))
                items.extend(self._collect_commits(owner, repo))
            except Exception as exc:
                errors.append(f"{target}: {exc}")

        return ConnectorBatch(
            connector_name="github",
            records_processed=len(items),
            items=items,
            errors=errors,
        )
