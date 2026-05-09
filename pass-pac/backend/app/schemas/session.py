from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    session_name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    mode: str = Field(default="simulator", min_length=1, max_length=50)
    environment: str = Field(default="local", min_length=1, max_length=50)


class SessionUpdate(BaseModel):
    session_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    mode: str | None = Field(default=None, min_length=1, max_length=50)
    environment: str | None = Field(default=None, min_length=1, max_length=50)


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_name: str
    description: str | None
    mode: str
    status: str
    environment: str
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
