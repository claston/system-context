from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.application import IntegrationTargetMappingService, SystemComponentNotFoundError
from app.dependencies import get_integration_target_mapping_service
from app.repositories import (
    DuplicateIntegrationTargetMappingError,
    IntegrationTargetMappingNotFoundError,
)
from app.schemas import (
    IntegrationTargetMappingCreate,
    IntegrationTargetMappingResponse,
    IntegrationTargetMappingUpdate,
)

router = APIRouter()


def _to_response(item) -> IntegrationTargetMappingResponse:
    return IntegrationTargetMappingResponse(
        id=item.id,
        connector_name=item.connector_name,
        external_target_id=item.external_target_id,
        external_target_name=item.external_target_name,
        system_component_id=item.system_component_id,
        environment=item.environment,
        metadata=item.metadata_json,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


@router.post(
    "/integration-target-mappings",
    response_model=IntegrationTargetMappingResponse,
    status_code=201,
)
def create_integration_target_mapping(
    payload: IntegrationTargetMappingCreate,
    service: IntegrationTargetMappingService = Depends(
        get_integration_target_mapping_service
    ),
):
    try:
        item = service.create(
            connector_name=payload.connector_name,
            external_target_id=payload.external_target_id,
            external_target_name=payload.external_target_name,
            system_component_id=payload.system_component_id,
            environment=payload.environment,
            metadata_json=payload.metadata,
            is_active=payload.is_active,
        )
        return _to_response(item)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
    except DuplicateIntegrationTargetMappingError:
        raise HTTPException(
            status_code=409,
            detail="Integration target mapping already exists",
        )


@router.get(
    "/integration-target-mappings",
    response_model=list[IntegrationTargetMappingResponse],
)
def list_integration_target_mappings(
    connector_name: str | None = Query(default=None),
    environment: str | None = Query(default=None),
    system_component_id: UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    service: IntegrationTargetMappingService = Depends(
        get_integration_target_mapping_service
    ),
):
    items = service.list(
        connector_name=connector_name,
        environment=environment,
        system_component_id=system_component_id,
        is_active=is_active,
    )
    return [_to_response(item) for item in items]


@router.get(
    "/integration-target-mappings/{mapping_id}",
    response_model=IntegrationTargetMappingResponse,
)
def get_integration_target_mapping(
    mapping_id: UUID,
    service: IntegrationTargetMappingService = Depends(
        get_integration_target_mapping_service
    ),
):
    try:
        return _to_response(service.get_by_id(mapping_id))
    except IntegrationTargetMappingNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Integration target mapping not found",
        )


@router.patch(
    "/integration-target-mappings/{mapping_id}",
    response_model=IntegrationTargetMappingResponse,
)
def patch_integration_target_mapping(
    mapping_id: UUID,
    payload: IntegrationTargetMappingUpdate,
    service: IntegrationTargetMappingService = Depends(
        get_integration_target_mapping_service
    ),
):
    try:
        update_data = payload.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["metadata_json"] = update_data.pop("metadata")
        item = service.update(
            mapping_id,
            **update_data,
        )
        return _to_response(item)
    except IntegrationTargetMappingNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Integration target mapping not found",
        )
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
    except DuplicateIntegrationTargetMappingError:
        raise HTTPException(
            status_code=409,
            detail="Integration target mapping already exists",
        )
