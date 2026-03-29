from pydantic import BaseModel
from pydantic import ConfigDict
from datetime import datetime
from uuid import UUID

class ServiceCreate(BaseModel):
    name: str
    description: str | None = None

class ServiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
