from __future__ import annotations

import glob
import json
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.proxmark_capabilities import (
    command_selector_map,
    commands_for_operation,
    normalize_registered_command,
    registered_commands,
)
from app.services.proxmark_parser import parse_identity_output
from app.services.proxmark_metadata_parser import parse_metadata_output
from app.services.proxmark_output_redaction import redact_proxmark_output

IDENTIFY_COMMANDS = command_selector_map("identify")
DIAGNOSTIC_COMMANDS = command_selector_map("diagnostic")
INSPECTION_COMMANDS = command_selector_map("inspect")
TRACE_COMMANDS = commands_for_operation("trace")
SAFE_COMMANDS = registered_commands()


def normalize_safe_command(command: str) -> str | None:
    return normalize_registered_command(command)


@dataclass(frozen=True)
class ProxmarkStatus:
    enabled: bool
    configured: bool
    connection_mode: str
    bridge_url: str | None
    bridge_available: bool
    client_path: str | None
    client_available: bool
    port: str | None
    detected_ports: list[str]
    safe_commands: list[str]
    integration_state: str
    notes: list[str]


@dataclass(frozen=True)
class ProxmarkProbeResult:
    command: str
    success: bool
    exit_code: int | None
    output: str
    error: str | None


@dataclass(frozen=True)
class ProxmarkIdentifyResult:
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


@dataclass(frozen=True)
class ProxmarkMetadataResult:
    command_key: str
    command: str
    success: bool
    exit_code: int | None
    fields: dict[str, Any]
    output: str
    error: str | None


class ProxmarkAdapter:
    def __init__(
        self,
        bridge_url: str | None,
        client_path: str | None,
        port: str | None,
        timeout_seconds: int = 10,
    ) -> None:
        self.bridge_url = bridge_url.rstrip("/") if bridge_url else None
        self.client_path = client_path
        self.port = port
        self.timeout_seconds = timeout_seconds

    def get_status(self) -> ProxmarkStatus:
        if self.bridge_url:
            return self._get_bridge_status()

        client_available = self._client_available()
        detected_ports = self.detect_ports()
        configured = bool(self.client_path and client_available)
        notes: list[str] = []

        if not self.client_path:
            notes.append("Set PROXMARK_CLIENT_PATH to the local pm3/proxmark3 client.")
        elif not client_available:
            notes.append("Configured Proxmark client path was not found.")

        if not self.port:
            notes.append(
                "Set PROXMARK_PORT when the device port is known, for example COM3 or /dev/ttyACM0."
            )

        notes.append(
            "Only registered diagnostics, identification, metadata reads, and passive trace views are enabled; state-changing workflows are blocked."
        )

        return ProxmarkStatus(
            enabled=configured,
            configured=configured,
            connection_mode="direct-client",
            bridge_url=None,
            bridge_available=False,
            client_path=self.client_path,
            client_available=client_available,
            port=self.port,
            detected_ports=detected_ports,
            safe_commands=SAFE_COMMANDS,
            integration_state="ready-to-probe" if configured else "configuration-required",
            notes=notes,
        )

    def probe_hw_version(self) -> ProxmarkProbeResult:
        command = "hw version"
        if command not in SAFE_COMMANDS:
            return ProxmarkProbeResult(command, False, None, "", "Command is not allowed.")

        if self.bridge_url:
            return self._probe_bridge()

        if not self.client_path or not self._client_available():
            return ProxmarkProbeResult(
                command,
                False,
                None,
                "",
                "Proxmark client is not configured or was not found.",
            )

        args = self._build_command(command)
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return ProxmarkProbeResult(
                command,
                False,
                None,
                exc.stdout or "",
                f"Command timed out after {self.timeout_seconds} seconds.",
            )
        except OSError as exc:
            return ProxmarkProbeResult(command, False, None, "", str(exc))

        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        )
        output = redact_proxmark_output(output, command)
        return ProxmarkProbeResult(
            command=command,
            success=completed.returncode == 0,
            exit_code=_normalize_exit_code(completed.returncode),
            output=output,
            error=None if completed.returncode == 0 else self._describe_probe_error(output),
        )

    def identify_card(self, technology: str) -> ProxmarkIdentifyResult:
        normalized_technology = technology.strip().lower()
        command = IDENTIFY_COMMANDS.get(normalized_technology)
        if command is None:
            return self._empty_identify_result(
                normalized_technology,
                "",
                "Unsupported identify technology. Use hf or lf.",
            )

        if self.bridge_url:
            return self._identify_bridge(normalized_technology)

        if not self.client_path or not self._client_available():
            return self._empty_identify_result(
                normalized_technology,
                command,
                "Proxmark client is not configured or was not found.",
            )

        try:
            completed = subprocess.run(
                self._build_command(command),
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return self._empty_identify_result(
                normalized_technology,
                command,
                f"Command timed out after {self.timeout_seconds} seconds.",
                output=exc.stdout or "",
            )
        except OSError as exc:
            return self._empty_identify_result(
                normalized_technology,
                command,
                str(exc),
            )

        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        )
        output = redact_proxmark_output(output, command)
        error = None
        if completed.returncode != 0:
            error = self._describe_probe_error(output)

        return self._build_identify_result(
            technology=normalized_technology,
            command=command,
            success=completed.returncode == 0,
            exit_code=_normalize_exit_code(completed.returncode),
            output=output,
            error=error,
        )

    def run_diagnostic(self, diagnostic: str) -> ProxmarkProbeResult:
        normalized_diagnostic = diagnostic.strip().lower()
        command = DIAGNOSTIC_COMMANDS.get(normalized_diagnostic)
        if command is None:
            return ProxmarkProbeResult(
                command="",
                success=False,
                exit_code=None,
                output="",
                error="Unsupported diagnostic. Use hardware_status or antenna_tune.",
            )

        if self.bridge_url:
            return self._diagnostic_bridge(normalized_diagnostic, command)

        if not self.client_path or not self._client_available():
            return ProxmarkProbeResult(
                command=command,
                success=False,
                exit_code=None,
                output="",
                error="Proxmark client is not configured or was not found.",
            )

        return self._run_local_command(command)

    def run_safe_command(self, command: str) -> ProxmarkProbeResult:
        canonical_command = normalize_safe_command(command)
        if canonical_command is None:
            return ProxmarkProbeResult(
                command=command.strip(),
                success=False,
                exit_code=None,
                output="",
                error="Command is not in the approved read-only allowlist.",
            )

        if self.bridge_url:
            return self._safe_command_bridge(canonical_command)

        if not self.client_path or not self._client_available():
            return ProxmarkProbeResult(
                command=canonical_command,
                success=False,
                exit_code=None,
                output="",
                error="Proxmark client is not configured or was not found.",
            )

        return self._run_local_command(canonical_command)

    def inspect_card(self, command_key: str) -> ProxmarkMetadataResult:
        normalized_key = command_key.strip().lower()
        command = INSPECTION_COMMANDS.get(normalized_key)
        if command is None:
            return ProxmarkMetadataResult(
                command_key=normalized_key,
                command="",
                success=False,
                exit_code=None,
                fields={},
                output="",
                error="Unsupported inspection command.",
            )

        if self.bridge_url:
            return self._inspect_bridge(normalized_key, command)

        if not self.client_path or not self._client_available():
            return ProxmarkMetadataResult(
                command_key=normalized_key,
                command=command,
                success=False,
                exit_code=None,
                fields={},
                output="",
                error="Proxmark client is not configured or was not found.",
            )

        result = self._run_local_command(command)
        return self._build_metadata_result(
            command_key=normalized_key,
            command=command,
            success=result.success,
            exit_code=result.exit_code,
            output=result.output,
            error=result.error,
        )

    def _run_local_command(self, command: str) -> ProxmarkProbeResult:
        try:
            completed = subprocess.run(
                self._build_command(command),
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return ProxmarkProbeResult(
                command,
                False,
                None,
                exc.stdout or "",
                f"Command timed out after {self.timeout_seconds} seconds.",
            )
        except OSError as exc:
            return ProxmarkProbeResult(command, False, None, "", str(exc))

        output = "\n".join(
            part for part in [completed.stdout.strip(), completed.stderr.strip()] if part
        )
        output = redact_proxmark_output(output, command)
        return ProxmarkProbeResult(
            command=command,
            success=completed.returncode == 0,
            exit_code=_normalize_exit_code(completed.returncode),
            output=output,
            error=None if completed.returncode == 0 else self._describe_probe_error(output),
        )

    def _build_command(self, command: str) -> list[str]:
        args = [self.client_path or "pm3"]
        if self.port:
            args.append(self.port)
        args.extend(["-c", command])
        return args

    def _client_available(self) -> bool:
        if not self.client_path:
            return False

        path = Path(self.client_path)
        return path.exists() or shutil.which(self.client_path) is not None

    def _get_bridge_status(self) -> ProxmarkStatus:
        try:
            payload = self._bridge_request("GET", "/status")
        except OSError as exc:
            return ProxmarkStatus(
                enabled=False,
                configured=False,
                connection_mode="windows-host-bridge",
                bridge_url=self.bridge_url,
                bridge_available=False,
                client_path=None,
                client_available=False,
                port=self.port,
                detected_ports=[],
                safe_commands=SAFE_COMMANDS,
                integration_state="bridge-unavailable",
                notes=[
                    f"Proxmark bridge is not reachable: {exc}",
                    "Start tools/proxmark_bridge.py on Windows, then refresh this status.",
                ],
            )

        return ProxmarkStatus(
            enabled=bool(payload.get("enabled")),
            configured=bool(payload.get("configured")),
            connection_mode=str(payload.get("connection_mode", "windows-host-bridge")),
            bridge_url=self.bridge_url,
            bridge_available=bool(payload.get("bridge_available", True)),
            client_path=_optional_str(payload.get("client_path")),
            client_available=bool(payload.get("client_available")),
            port=_optional_str(payload.get("port")),
            detected_ports=_as_string_list(payload.get("detected_ports")),
            safe_commands=_as_string_list(payload.get("safe_commands")) or SAFE_COMMANDS,
            integration_state=str(payload.get("integration_state", "configuration-required")),
            notes=_as_string_list(payload.get("notes")),
        )

    def _probe_bridge(self) -> ProxmarkProbeResult:
        try:
            payload = self._bridge_request("POST", "/probe")
        except OSError as exc:
            return ProxmarkProbeResult(
                command="hw version",
                success=False,
                exit_code=None,
                output="",
                error=f"Proxmark bridge is not reachable: {exc}",
            )

        exit_code = payload.get("exit_code")
        return ProxmarkProbeResult(
            command=str(payload.get("command", "hw version")),
            success=bool(payload.get("success")),
            exit_code=exit_code if isinstance(exit_code, int) else None,
            output=str(payload.get("output") or ""),
            error=_optional_str(payload.get("error")),
        )

    def _diagnostic_bridge(
        self,
        diagnostic: str,
        command: str,
    ) -> ProxmarkProbeResult:
        try:
            payload = self._bridge_request(
                "POST",
                "/diagnostic",
                payload={"diagnostic": diagnostic},
            )
        except OSError as exc:
            return ProxmarkProbeResult(
                command=command,
                success=False,
                exit_code=None,
                output="",
                error=f"Proxmark bridge is not reachable: {exc}",
            )

        exit_code = payload.get("exit_code")
        return ProxmarkProbeResult(
            command=str(payload.get("command", command)),
            success=bool(payload.get("success")),
            exit_code=exit_code if isinstance(exit_code, int) else None,
            output=str(payload.get("output") or ""),
            error=_optional_str(payload.get("error")),
        )

    def _safe_command_bridge(self, command: str) -> ProxmarkProbeResult:
        if command == "hw version":
            return self._probe_bridge()
        if command in DIAGNOSTIC_COMMANDS.values():
            diagnostic = next(
                key for key, value in DIAGNOSTIC_COMMANDS.items() if value == command
            )
            return self._diagnostic_bridge(diagnostic, command)
        if command in IDENTIFY_COMMANDS.values():
            technology = next(
                key for key, value in IDENTIFY_COMMANDS.items() if value == command
            )
            result = self._identify_bridge(technology)
            return ProxmarkProbeResult(
                command=result.command,
                success=result.success,
                exit_code=result.exit_code,
                output=result.output,
                error=result.error,
            )
        if command in INSPECTION_COMMANDS.values():
            command_key = next(
                key for key, value in INSPECTION_COMMANDS.items() if value == command
            )
            result = self._inspect_bridge(command_key, command)
            return ProxmarkProbeResult(
                command=result.command,
                success=result.success,
                exit_code=result.exit_code,
                output=result.output,
                error=result.error,
            )

        try:
            payload = self._bridge_request(
                "POST",
                "/command",
                payload={"command": command},
            )
        except OSError as exc:
            return ProxmarkProbeResult(
                command=command,
                success=False,
                exit_code=None,
                output="",
                error=f"Proxmark bridge is not reachable: {exc}",
            )

        exit_code = payload.get("exit_code")
        return ProxmarkProbeResult(
            command=str(payload.get("command", command)),
            success=bool(payload.get("success")),
            exit_code=exit_code if isinstance(exit_code, int) else None,
            output=str(payload.get("output") or ""),
            error=_optional_str(payload.get("error")),
        )

    def _inspect_bridge(
        self,
        command_key: str,
        command: str,
    ) -> ProxmarkMetadataResult:
        try:
            payload = self._bridge_request(
                "POST",
                "/inspect",
                payload={"command_key": command_key},
            )
        except OSError as exc:
            return ProxmarkMetadataResult(
                command_key=command_key,
                command=command,
                success=False,
                exit_code=None,
                fields={},
                output="",
                error=f"Proxmark bridge is not reachable: {exc}",
            )

        exit_code = payload.get("exit_code")
        return self._build_metadata_result(
            command_key=command_key,
            command=str(payload.get("command", command)),
            success=bool(payload.get("success")),
            exit_code=exit_code if isinstance(exit_code, int) else None,
            output=str(payload.get("output") or ""),
            error=_optional_str(payload.get("error")),
        )

    @staticmethod
    def _build_metadata_result(
        command_key: str,
        command: str,
        success: bool,
        exit_code: int | None,
        output: str,
        error: str | None,
    ) -> ProxmarkMetadataResult:
        parsed = parse_metadata_output(command_key, output)
        return ProxmarkMetadataResult(
            command_key=command_key,
            command=command,
            success=success,
            exit_code=exit_code,
            fields=parsed.fields,
            output=output,
            error=error,
        )

    def _identify_bridge(self, technology: str) -> ProxmarkIdentifyResult:
        command = IDENTIFY_COMMANDS[technology]
        try:
            payload = self._bridge_request(
                "POST",
                "/identify",
                payload={"technology": technology},
            )
        except OSError as exc:
            return self._empty_identify_result(
                technology=technology,
                command=command,
                error=f"Proxmark bridge is not reachable: {exc}",
            )

        exit_code = payload.get("exit_code")
        return self._build_identify_result(
            technology=technology,
            command=str(payload.get("command", command)),
            success=bool(payload.get("success")),
            exit_code=exit_code if isinstance(exit_code, int) else None,
            output=str(payload.get("output") or ""),
            error=_optional_str(payload.get("error")),
        )

    def _bridge_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.bridge_url:
            raise OSError("Bridge URL is not configured.")

        request_body = None
        if payload is not None:
            request_body = json.dumps(payload).encode("utf-8")
        elif method == "POST":
            request_body = b""

        request = urllib.request.Request(
            f"{self.bridge_url}{path}",
            data=request_body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            raise OSError(str(exc.reason)) from exc

        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise OSError("Bridge returned an invalid response.")
        if isinstance(payload.get("output"), str):
            payload["output"] = redact_proxmark_output(
                payload["output"],
                str(payload.get("command") or ""),
            )
        return payload

    def _build_identify_result(
        self,
        technology: str,
        command: str,
        success: bool,
        exit_code: int | None,
        output: str,
        error: str | None,
    ) -> ProxmarkIdentifyResult:
        output = redact_proxmark_output(output, command)
        parsed = parse_identity_output(technology, output)
        return ProxmarkIdentifyResult(
            technology=technology,
            command=command,
            success=success,
            exit_code=exit_code,
            detected=success and parsed.detected,
            card_type=parsed.card_type,
            protocol=parsed.protocol,
            uid=parsed.uid,
            atqa=parsed.atqa,
            sak=parsed.sak,
            fields=parsed.fields,
            output=output,
            error=error,
        )

    def _empty_identify_result(
        self,
        technology: str,
        command: str,
        error: str,
        output: str = "",
    ) -> ProxmarkIdentifyResult:
        parsed = parse_identity_output(technology, output)
        return ProxmarkIdentifyResult(
            technology=technology,
            command=command,
            success=False,
            exit_code=None,
            detected=False,
            card_type=parsed.card_type,
            protocol=parsed.protocol,
            uid=parsed.uid,
            atqa=parsed.atqa,
            sak=parsed.sak,
            fields=parsed.fields,
            output=output,
            error=error,
        )

    def _describe_probe_error(self, output: str) -> str:
        if "invalid serial port" in output.lower():
            port = self.port or "the configured port"
            return (
                f"The Proxmark client could not open {port}. "
                "Close any existing Proxmark/Phosphor/pm3 window using the device, "
                "confirm the USB cable is connected, then retry."
            )
        if "no data found" in output.lower() or "couldn't identify a chipset" in output.lower():
            return "No matching card was identified by this read-only command."
        if "command execution time out" in output.lower():
            return "The Proxmark command timed out while searching for a card."
        return "Proxmark client returned a non-zero exit code."

    @staticmethod
    def detect_ports() -> list[str]:
        patterns = [
            "/dev/ttyACM*",
            "/dev/ttyUSB*",
            "/dev/cu.usbmodem*",
            "/dev/cu.usbserial*",
        ]
        ports = sorted({port for pattern in patterns for port in glob.glob(pattern)})
        return ports


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _normalize_exit_code(exit_code: int) -> int:
    if exit_code > 2_147_483_647:
        return exit_code - 4_294_967_296
    return exit_code
