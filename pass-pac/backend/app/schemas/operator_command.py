from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OperatorCommandCreate(BaseModel):
    command: str = Field(..., min_length=1, max_length=120)


class OperatorCommandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    command: str
    status: str
    success: bool
    exit_code: int | None
    output: str
    error: str | None
    created_at: datetime


class OperatorRecipeResponse(BaseModel):
    key: str
    name: str
    description: str
    protocol: str
    safety_tier: str
    command_keys: list[str]
    commands: list[str]
    expected_evidence: list[str]


class OperatorRecipeRunResponse(BaseModel):
    recipe: OperatorRecipeResponse
    status: str
    command_count: int
    successful_count: int
    results: list[OperatorCommandResponse]


class CommandCapabilityResponse(BaseModel):
    key: str
    command: str
    name: str
    protocol: str
    category: str
    safety_tier: str
    operation: str
    selector: str
    read_only: bool
    changes_state: bool
    expected_evidence: list[str]


class CapabilityRegistryResponse(BaseModel):
    version: str
    scope: str
    commands: list[CommandCapabilityResponse]
    recipes: list[OperatorRecipeResponse]
