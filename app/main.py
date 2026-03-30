from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.application import SystemComponentNotFoundError, SystemComponentService
from app.db import SessionLocal
from app.repositories import (
    DuplicateSystemComponentNameError,
    SqlAlchemySystemComponentRepository,
    SystemComponentRepository,
)
from app.schemas import SystemComponentCreate, SystemComponentResponse

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_system_component_repository(
    db: Session = Depends(get_db),
) -> SystemComponentRepository:
    return SqlAlchemySystemComponentRepository(db)


def get_system_component_service(
    repository: SystemComponentRepository = Depends(get_system_component_repository),
) -> SystemComponentService:
    return SystemComponentService(repository)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/system-components", response_model=SystemComponentResponse)
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


@app.get("/system-components", response_model=list[SystemComponentResponse])
def list_system_components(
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    return component_service.list()


@app.get("/system-components/{system_component_id}", response_model=SystemComponentResponse)
def get_system_component(
    system_component_id: UUID,
    component_service: SystemComponentService = Depends(get_system_component_service),
):
    try:
        return component_service.get_by_id(system_component_id)
    except SystemComponentNotFoundError:
        raise HTTPException(status_code=404, detail="System component not found")
