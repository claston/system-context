from datetime import datetime, timedelta, timezone

from app.application.system_component_service import SystemComponentNotFoundError
from app.repositories import ContextQueryRepository


class ContextService:
    def __init__(self, context_query_repository: ContextQueryRepository) -> None:
        self.context_query_repository = context_query_repository

    def list_system_component_names(self) -> list[str]:
        return self.context_query_repository.list_system_component_names()

    def list_known_environments(self) -> list[str]:
        return self.context_query_repository.list_known_environments()

    def get_system_current_state(self):
        return {
            "system_component_count": self.context_query_repository.count_system_components(),
            "code_repo_count": self.context_query_repository.count_code_repos(),
            "deployment_count": self.context_query_repository.count_deployments(),
            "runtime_snapshot_count": self.context_query_repository.count_runtime_snapshots(),
        }

    def get_system_component_context(self, system_component_name: str, environment: str | None = None):
        system_component = self.context_query_repository.get_system_component_by_name(
            system_component_name
        )
        if not system_component:
            raise SystemComponentNotFoundError

        now = datetime.now(timezone.utc)
        latest_deployment = self.context_query_repository.get_latest_deployment_for_system_component(
            system_component.id, environment
        )
        latest_runtime = self.context_query_repository.get_latest_runtime_for_system_component(
            system_component.id, environment
        )
        deps = self.context_query_repository.get_dependencies_for_system_component(
            system_component.id
        )
        latest_unexpected_restart = (
            self.context_query_repository.get_latest_unexpected_restart_for_system_component(
                system_component.id, environment
            )
        )
        app_up = self._resolve_app_up(latest_runtime)

        return {
            "system_component": system_component.name,
            "environment": environment,
            "latest_deployment_version": latest_deployment.version if latest_deployment else None,
            "latest_runtime_health": latest_runtime.health_status if latest_runtime else None,
            "app_up": app_up,
            "recent_pull_requests": self.context_query_repository.get_recent_pull_requests_count_for_system_component(
                system_component.id
            ),
            "recent_commits": self.context_query_repository.get_recent_commits_count_for_system_component(
                system_component.id
            ),
            "dependencies": [str(dep.target_system_component_id) for dep in deps],
            "open_operational_issues": self.context_query_repository.count_open_operational_issues_for_system_component(
                system_component.id, environment
            ),
            "unexpected_restarts_last_24h": self.context_query_repository.count_unexpected_restarts_for_system_component(
                system_component.id,
                now - timedelta(hours=24),
                environment,
            ),
            "last_unexpected_restart_at": latest_unexpected_restart.last_seen_at
            if latest_unexpected_restart
            else None,
        }

    def _resolve_app_up(self, latest_runtime) -> bool:
        if latest_runtime is None:
            return False
        health_status = str(getattr(latest_runtime, "health_status", "") or "").strip().lower()
        if health_status in {"down", "failed", "suspended", "stopped", "error", "dead"}:
            return False
        if health_status:
            return True
        pod_count = getattr(latest_runtime, "pod_count", None)
        return isinstance(pod_count, int) and pod_count > 0
