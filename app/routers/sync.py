from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.application import (
    SyncRunNotFoundError,
    SyncService,
    SyncShuttingDownError,
    UnknownConnectorError,
)
from app.connectors.base import ConnectorRunRequest
from app.dependencies import get_sync_service
from app.schemas import SyncRunResponse, SyncRunTriggerRequest

router = APIRouter()


@router.post("/sync-runs/{connector_name}", response_model=SyncRunResponse)
def run_sync(
    connector_name: str,
    payload: SyncRunTriggerRequest,
    sync_service: SyncService = Depends(get_sync_service),
):
    try:
        return sync_service.trigger_sync(
            connector_name=connector_name,
            request=ConnectorRunRequest(system_component_name=payload.system_component_name),
        )
    except UnknownConnectorError:
        raise HTTPException(status_code=404, detail="Connector not found")
    except SyncShuttingDownError:
        raise HTTPException(status_code=503, detail="Sync service is shutting down")


@router.get("/sync-runs/{sync_run_id}", response_model=SyncRunResponse)
def get_sync_run(sync_run_id: UUID, sync_service: SyncService = Depends(get_sync_service)):
    try:
        return sync_service.get_sync_run(sync_run_id)
    except SyncRunNotFoundError:
        raise HTTPException(status_code=404, detail="Sync run not found")
