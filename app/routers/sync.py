from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.application import SyncRunNotFoundError, SyncService
from app.dependencies import get_sync_service
from app.schemas import GithubSyncRunRequest, SyncRunResponse

router = APIRouter()


@router.post("/sync-runs/github", response_model=SyncRunResponse)
def run_github_sync(
    payload: GithubSyncRunRequest,
    sync_service: SyncService = Depends(get_sync_service),
):
    return sync_service.trigger_github_sync(system_component_name=payload.system_component_name)


@router.get("/sync-runs/{sync_run_id}", response_model=SyncRunResponse)
def get_sync_run(sync_run_id: UUID, sync_service: SyncService = Depends(get_sync_service)):
    try:
        return sync_service.get_sync_run(sync_run_id)
    except SyncRunNotFoundError:
        raise HTTPException(status_code=404, detail="Sync run not found")
