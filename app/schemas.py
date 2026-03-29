from pydantic import BaseModel
from datetime import datetime
from uuid import UUID

class ServiceCreate(BaseModel):
    name: str
    description: str | None = None

class ServiceResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime