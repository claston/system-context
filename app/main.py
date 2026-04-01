from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.dependencies import get_code_repo_service, get_db, get_system_component_service
from app.routers import (
    code_repos_router,
    context_entities_router,
    context_queries_router,
    system_components_router,
)

app = FastAPI()
app.include_router(system_components_router)
app.include_router(code_repos_router)
app.include_router(context_entities_router)
app.include_router(context_queries_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={
            "detail": "Validation failed",
            "errors": jsonable_encoder(exc.errors()),
        },
    )

__all__ = [
    "app",
    "get_db",
    "get_system_component_service",
    "get_code_repo_service",
]
