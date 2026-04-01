from fastapi import APIRouter, Depends

from app.application import SyncService
from app.dependencies import get_sync_service
from app.schemas import GithubSyncRunRequest, SyncRunResponse

router = APIRouter()


@router.post("/sync-runs/github", response_model=SyncRunResponse)
def run_github_sync(
    payload: GithubSyncRunRequest,
    sync_service: SyncService = Depends(get_sync_service),
):
    return sync_service.run_github_sync(system_component_name=payload.system_component_name)
