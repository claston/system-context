from app import dependencies
from app.main import app, get_code_repo_service, get_db, get_system_component_service


def test_main_reexports_dependency_functions() -> None:
    assert get_db is dependencies.get_db
    assert get_system_component_service is dependencies.get_system_component_service
    assert get_code_repo_service is dependencies.get_code_repo_service


def test_app_has_refactored_route_surface() -> None:
    paths = {route.path for route in app.routes}

    expected_paths = {
        "/health",
        "/release-check",
        "/system-components",
        "/system-components/{system_component_id}",
        "/system-components/{system_component_id}/code-repos",
        "/code-repos",
        "/code-repos/{code_repo_id}",
        "/integration-target-mappings",
        "/integration-target-mappings/{mapping_id}",
        "/pull-requests",
        "/commits",
        "/deployments",
        "/runtime-snapshots",
        "/api-contracts",
        "/endpoints",
        "/dependencies",
        "/sync-runs",
        "/context/system/current-state",
        "/context/system-component/{name}",
        "/context/system-component/{name}/changes",
        "/context/system-component/{name}/runtime",
        "/context/system-component/{name}/dependencies",
        "/agent/context",
        "/mcp",
    }

    assert expected_paths.issubset(paths)
