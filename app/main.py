from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.repositories import (
    DuplicateServiceNameError,
    ServiceRepository,
    SqlAlchemyServiceRepository,
)
from app.schemas import ServiceCreate, ServiceResponse

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_service_repository(db: Session = Depends(get_db)) -> ServiceRepository:
    return SqlAlchemyServiceRepository(db)


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/services", response_model=ServiceResponse)
def create_service(
    service: ServiceCreate,
    repository: ServiceRepository = Depends(get_service_repository),
):
    try:
        return repository.create(name=service.name, description=service.description)
    except DuplicateServiceNameError as exc:
        raise HTTPException(status_code=409, detail="Service name already exists") from exc

@app.get("/services", response_model=list[ServiceResponse])
def list_services(repository: ServiceRepository = Depends(get_service_repository)):
    return repository.list()

@app.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(
    service_id: UUID, repository: ServiceRepository = Depends(get_service_repository)
):
    service = repository.get_by_id(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service
