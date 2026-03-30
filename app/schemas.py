from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SystemComponentCreate(BaseModel):
    name: str
    description: str | None = None


class SystemComponentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class CodeRepoCreate(BaseModel):
    system_component_id: UUID
    provider: str
    name: str
    url: str
    default_branch: str | None = None


class CodeRepoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    system_component_id: UUID
    provider: str
    name: str
    url: str
    default_branch: str | None = None
    created_at: datetime
    updated_at: datetime
