from fastapi import APIRouter, Depends, HTTPException

from app.application import ContextService, SystemComponentNotFoundError
from app.dependencies import get_context_service
from app.schemas import AgentContextRequest, AgentContextResponse

router = APIRouter()


@router.get("/context/system/current-state")
def get_system_current_state(
    context_service: ContextService = Depends(get_context_service),
):
    return context_service.get_system_current_state()


@router.get("/context/system-component/{name}", response_model=AgentContextResponse)
def get_system_component_context(
    name: str,
    environment: str | None = None,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        return context_service.get_system_component_context(name, environment)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@router.get("/context/system-component/{name}/changes")
def get_system_component_changes(
    name: str,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        context = context_service.get_system_component_context(name)
        return {
            "system_component": context["system_component"],
            "recent_pull_requests": context["recent_pull_requests"],
            "recent_commits": context["recent_commits"],
        }
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@router.get("/context/system-component/{name}/runtime")
def get_system_component_runtime(
    name: str,
    environment: str | None = None,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        context = context_service.get_system_component_context(name, environment)
        return {
            "system_component": context["system_component"],
            "environment": context["environment"],
            "latest_runtime_health": context["latest_runtime_health"],
            "latest_deployment_version": context["latest_deployment_version"],
        }
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@router.get("/context/system-component/{name}/dependencies")
def get_system_component_dependencies(
    name: str,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        context = context_service.get_system_component_context(name)
        return {
            "system_component": context["system_component"],
            "dependencies": context["dependencies"],
        }
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")


@router.post("/agent/context", response_model=AgentContextResponse)
def post_agent_context(
    payload: AgentContextRequest,
    context_service: ContextService = Depends(get_context_service),
):
    try:
        return context_service.get_system_component_context(
            payload.system_component_name,
            payload.environment,
        )
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
