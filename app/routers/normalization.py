from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.application import (
    GithubNormalizationService,
    NormalizationSyncRunNotFoundError,
    UnsupportedNormalizationConnectorError,
)
from app.dependencies import get_github_normalization_service
from app.schemas import GithubNormalizationResponse

router = APIRouter()


@router.post(
    "/normalize/github/sync-runs/{sync_run_id}",
    response_model=GithubNormalizationResponse,
)
def normalize_github_sync_run(
    sync_run_id: UUID,
    normalization_service: GithubNormalizationService = Depends(
        get_github_normalization_service
    ),
):
    try:
        return normalization_service.normalize_sync_run(sync_run_id)
    except NormalizationSyncRunNotFoundError:
        raise HTTPException(status_code=404, detail="Sync run not found")
    except UnsupportedNormalizationConnectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
