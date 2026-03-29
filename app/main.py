from uuid import UUID
from fastapi import FastAPI, HTTPException
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Service
from app.schemas import ServiceCreate, ServiceResponse

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/services", response_model=ServiceResponse)
def create_service(service: ServiceCreate, db: Session = Depends(get_db)):
    service = Service(name=service.name, description=service.description)
    db.add(service)
    db.commit()
    db.refresh(service)
    return service

@app.get("/services", response_model=list[ServiceResponse])
def list_services(db: Session = Depends(get_db)):
    services = db.query(Service).all()
    return services

@app.get("/services/{service_id}", response_model=ServiceResponse)
def get_service(service_id: UUID, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service