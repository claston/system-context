from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.repositories import GithubNormalizationRepository


class NormalizationSyncRunNotFoundError(Exception):
    pass


class UnsupportedNormalizationConnectorError(Exception):
    pass


class GithubNormalizationService:
    def __init__(self, normalization_repository: GithubNormalizationRepository) -> None:
        self.normalization_repository = normalization_repository

    def normalize_sync_run(self, sync_run_id: UUID) -> dict[str, Any]:
        sync_run = self.normalization_repository.get_sync_run_by_id(sync_run_id)
        if sync_run is None:
            raise NormalizationSyncRunNotFoundError(
                f"sync run not found: {sync_run_id}"
            )

        connector_name = self._get_value(sync_run, "connector_name")
        if connector_name != "github":
            raise UnsupportedNormalizationConnectorError(
                f"unsupported connector for github normalization: {connector_name}"
            )

        raw_events = self.normalization_repository.list_connector_raw_events_by_sync_run(
            sync_run_id=sync_run_id,
            connector_name="github",
        )
        code_repo_cache: dict[str, Any | None] = {}
        summary = {
            "sync_run_id": sync_run_id,
            "connector_name": "github",
            "raw_events_read": len(raw_events),
            "pull_requests_created": 0,
            "pull_requests_updated": 0,
            "commits_created": 0,
            "commits_updated": 0,
            "skipped": 0,
            "errors": [],
        }

        for raw_event in raw_events:
            payload = self._get_value(raw_event, "payload")
            if not isinstance(payload, dict):
                summary["skipped"] += 1
                summary["errors"].append(
                    f"raw event {self._get_value(raw_event, 'id')} has invalid payload"
                )
                continue

            kind = str(payload.get("kind") or "").strip()
            repository_name = str(payload.get("repository") or "").strip()
            if kind not in {"pull_request", "commit"}:
                summary["skipped"] += 1
                continue
            if not repository_name:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"missing repository for raw event {self._get_value(raw_event, 'id')}"
                )
                continue

            if repository_name not in code_repo_cache:
                code_repo_cache[repository_name] = (
                    self.normalization_repository.get_code_repo_by_provider_and_repository(
                        provider="github",
                        repository=repository_name,
                    )
                )
            code_repo = code_repo_cache[repository_name]
            if code_repo is None:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"code repo not found for repository {repository_name}"
                )
                continue

            code_repo_id = self._get_value(code_repo, "id")
            try:
                if kind == "pull_request":
                    was_created = self._normalize_pull_request(
                        code_repo_id=code_repo_id,
                        payload=payload,
                    )
                    if was_created:
                        summary["pull_requests_created"] += 1
                    else:
                        summary["pull_requests_updated"] += 1
                else:
                    was_created = self._normalize_commit(
                        code_repo_id=code_repo_id,
                        payload=payload,
                    )
                    if was_created:
                        summary["commits_created"] += 1
                    else:
                        summary["commits_updated"] += 1
            except Exception as exc:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"{repository_name}/{kind}: {type(exc).__name__}: {exc}"
                )

        return summary

    def _normalize_pull_request(self, code_repo_id: UUID, payload: dict[str, Any]) -> bool:
        number_value = payload.get("number")
        number = str(number_value).strip() if number_value is not None else ""
        if not number:
            raise ValueError("pull request number is required")

        title = str(payload.get("title") or "").strip() or "(untitled pull request)"
        merged_at = self._parse_iso_datetime(payload.get("merged_at"))
        state = str(payload.get("state") or "open").strip() or "open"
        status = "merged" if merged_at is not None else state
        data: dict[str, Any] = {
            "code_repo_id": code_repo_id,
            "number": number,
            "title": title,
            "status": status,
            "author": self._optional_string(payload.get("author")),
            "url": self._optional_string(payload.get("url")),
            "merged_at": merged_at,
        }

        existing = self.normalization_repository.get_pull_request_by_repo_and_number(
            code_repo_id=code_repo_id,
            number=number,
        )
        if existing is None:
            self.normalization_repository.create_pull_request(**data)
            return True

        pull_request_id = self._get_value(existing, "id")
        self.normalization_repository.update_pull_request(pull_request_id, **data)
        return False

    def _normalize_commit(self, code_repo_id: UUID, payload: dict[str, Any]) -> bool:
        sha_value = payload.get("sha") or payload.get("id")
        sha = str(sha_value).strip() if sha_value is not None else ""
        if not sha:
            raise ValueError("commit sha is required")

        data: dict[str, Any] = {
            "code_repo_id": code_repo_id,
            "sha": sha,
            "message": str(payload.get("message") or "").strip() or "(no message)",
            "author": self._optional_string(payload.get("author")),
        }
        committed_at = self._parse_iso_datetime(payload.get("committed_at"))
        if committed_at is not None:
            data["committed_at"] = committed_at

        existing = self.normalization_repository.get_commit_by_repo_and_sha(
            code_repo_id=code_repo_id,
            sha=sha,
        )
        if existing is None:
            self.normalization_repository.create_commit(**data)
            return True

        commit_id = self._get_value(existing, "id")
        self.normalization_repository.update_commit(commit_id, **data)
        return False

    def _parse_iso_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized

    def _get_value(self, item: Any, field: str) -> Any:
        if isinstance(item, dict):
            return item.get(field)
        return getattr(item, field, None)
