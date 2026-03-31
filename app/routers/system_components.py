from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.application import SystemComponentNotFoundError, SystemComponentService
from app.dependencies import get_system_component_service
from app.repositories import DuplicateSystemComponentNameError
from app.schemas import SystemComponentCreate, SystemComponentResponse

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/system-components", response_model=SystemComponentResponse)
def create_system_component(
    system_component: SystemComponentCreate,
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    try:
        return component_service.create(
            name=system_component.name,
            description=system_component.description,
        )
    except DuplicateSystemComponentNameError as exc:
        raise HTTPException(
            status_code=409,
            detail="System component name already exists",
        ) from exc


@router.get("/system-components", response_model=list[SystemComponentResponse])
def list_system_components(
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    return component_service.list()


@router.get("/system-components/{system_component_id}", response_model=SystemComponentResponse)
def get_system_component(
    system_component_id: UUID,
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    try:
        return component_service.get_by_id(system_component_id)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
