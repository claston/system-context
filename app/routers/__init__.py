from app.routers.code_repos import router as code_repos_router
from app.routers.context_entities import router as context_entities_router
from app.routers.context_queries import router as context_queries_router
from app.routers.normalization import router as normalization_router
from app.routers.sync import router as sync_router
from app.routers.system_components import router as system_components_router

__all__ = [
    "code_repos_router",
    "context_entities_router",
    "context_queries_router",
    "normalization_router",
    "sync_router",
    "system_components_router",
]
