from typing import Any

from pydantic import BaseModel, ConfigDict


class ProxmarkStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    configured: bool
    connection_mode: str
    bridge_url: str | None = None
    bridge_available: bool
    client_path: str | None
    client_available: bool
    port: str | None
    detected_ports: list[str]
    safe_commands: list[str]
    integration_state: str
    notes: list[str]


class ProxmarkProbeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    command: str
    success: bool
    exit_code: int | None
    output: str
    error: str | None


class ProxmarkIdentifyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    technology: str
    command: str
    success: bool
    exit_code: int | None
    detected: bool
    card_type: str | None
    protocol: str | None
    uid: str | None
    atqa: str | None
    sak: str | None
    fields: dict[str, str]
    output: str
    error: str | None
    saved_observation_path: str | None = None


class ProxmarkMetadataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    command_key: str
    command: str
    success: bool
    exit_code: int | None
    fields: dict[str, Any]
    output: str
    error: str | None
