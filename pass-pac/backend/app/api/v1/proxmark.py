from dataclasses import asdict, replace

from fastapi import APIRouter

from app.adapters.proxmark_adapter import ProxmarkAdapter
from app.core.config import get_settings
from app.schemas.proxmark import (
    ProxmarkIdentifyResponse,
    ProxmarkMetadataResponse,
    ProxmarkProbeResponse,
    ProxmarkStatusResponse,
)
from app.services.observation_store import append_live_card_observation

router = APIRouter(prefix="/device/proxmark", tags=["proxmark"])


@router.get("/status", response_model=ProxmarkStatusResponse)
def read_proxmark_status() -> ProxmarkStatusResponse:
    settings = get_settings()
    adapter = ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )
    return ProxmarkStatusResponse.model_validate(adapter.get_status())


@router.post("/probe", response_model=ProxmarkProbeResponse)
def probe_proxmark_device() -> ProxmarkProbeResponse:
    settings = get_settings()
    adapter = ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )
    return ProxmarkProbeResponse.model_validate(adapter.probe_hw_version())


@router.post("/diagnostic/{diagnostic}", response_model=ProxmarkProbeResponse)
def run_proxmark_diagnostic(diagnostic: str) -> ProxmarkProbeResponse:
    settings = get_settings()
    adapter = ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )
    return ProxmarkProbeResponse.model_validate(adapter.run_diagnostic(diagnostic))


@router.post("/inspect/{command_key}", response_model=ProxmarkMetadataResponse)
def inspect_proxmark_card(command_key: str) -> ProxmarkMetadataResponse:
    settings = get_settings()
    adapter = ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )
    return ProxmarkMetadataResponse.model_validate(adapter.inspect_card(command_key))


@router.post("/identify/hf", response_model=ProxmarkIdentifyResponse)
def identify_hf_card() -> ProxmarkIdentifyResponse:
    return _identify_card("hf")


@router.post("/identify/lf", response_model=ProxmarkIdentifyResponse)
def identify_lf_card() -> ProxmarkIdentifyResponse:
    return _identify_card("lf")


def _identify_card(technology: str) -> ProxmarkIdentifyResponse:
    settings = get_settings()
    adapter = ProxmarkAdapter(
        bridge_url=settings.proxmark_bridge_url,
        client_path=settings.proxmark_client_path,
        port=settings.proxmark_port,
        timeout_seconds=settings.proxmark_command_timeout_seconds,
    )
    result = adapter.identify_card(technology)

    if result.success and result.detected:
        saved_path = append_live_card_observation(
            mock_data_dir=settings.mock_data_dir,
            observation=asdict(result),
        )
        result = replace(result, saved_observation_path=saved_path)

    return ProxmarkIdentifyResponse.model_validate(result)
