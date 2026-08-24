#!/usr/bin/env python3
"""Local Windows bridge for safe Proxmark3 status and identify probing.

The Docker backend cannot reliably access Windows USB serial devices directly.
Run this script on the Windows host, then let the backend call it through
http://host.docker.internal:8765.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.core.proxmark_capabilities import (  # noqa: E402
    command_selector_map,
    commands_for_operation,
    normalize_registered_command,
    registered_commands,
)
from app.services.proxmark_output_redaction import redact_proxmark_output  # noqa: E402

IDENTIFY_COMMANDS = command_selector_map("identify")
DIAGNOSTIC_COMMANDS = command_selector_map("diagnostic")
INSPECTION_COMMANDS = command_selector_map("inspect")
TRACE_COMMANDS = commands_for_operation("trace")
SAFE_COMMANDS = registered_commands()


def normalize_safe_command(command: str) -> str | None:
    return normalize_registered_command(command)


class BridgeState:
    def __init__(
        self,
        client_path: str,
        device_port: str,
        timeout_seconds: int,
    ) -> None:
        self.client_path = client_path
        self.device_port = device_port
        self.timeout_seconds = timeout_seconds
        self._command_lock = Lock()

    @property
    def client_available(self) -> bool:
        return Path(self.client_path).exists() or shutil.which(self.client_path) is not None

    def status(self) -> dict[str, Any]:
        notes = [
            "Windows host bridge is active.",
            "Only registered diagnostics, identification, metadata reads, and passive trace views are exposed.",
            "State-changing, key-recovery, simulation, and write workflows are blocked by this bridge.",
        ]
        if not self.client_available:
            notes.insert(0, "Configured Proxmark client path was not found.")
        if not self.device_port:
            notes.insert(0, "Device port is not configured.")

        configured = self.client_available and bool(self.device_port)
        return {
            "enabled": configured,
            "configured": configured,
            "connection_mode": "windows-host-bridge",
            "bridge_available": True,
            "client_path": self.client_path,
            "client_available": self.client_available,
            "port": self.device_port,
            "detected_ports": [self.device_port] if self.device_port else [],
            "safe_commands": SAFE_COMMANDS,
            "integration_state": "ready-to-probe" if configured else "configuration-required",
            "busy": self._command_lock.locked(),
            "notes": notes,
        }

    def probe_hw_version(self) -> dict[str, Any]:
        return self._run_allowed_command("hw version")

    def identify_card(self, technology: str) -> dict[str, Any]:
        normalized_technology = technology.strip().lower()
        command = IDENTIFY_COMMANDS.get(normalized_technology)
        if command is None:
            return {
                "technology": normalized_technology,
                "command": "",
                "success": False,
                "exit_code": None,
                "output": "",
                "error": "Unsupported identify technology. Use hf or lf.",
            }

        result = self._run_allowed_command(command)
        return {
            "technology": normalized_technology,
            **result,
        }

    def run_diagnostic(self, diagnostic: str) -> dict[str, Any]:
        normalized_diagnostic = diagnostic.strip().lower()
        command = DIAGNOSTIC_COMMANDS.get(normalized_diagnostic)
        if command is None:
            return {
                "command": "",
                "success": False,
                "exit_code": None,
                "output": "",
                "error": "Unsupported diagnostic. Use hardware_status or antenna_tune.",
            }
        return self._run_allowed_command(command)

    def run_safe_command(self, command: str) -> dict[str, Any]:
        canonical_command = normalize_safe_command(command)
        if canonical_command is None:
            return {
                "command": command.strip(),
                "success": False,
                "exit_code": None,
                "output": "",
                "error": "Command is not in the approved read-only allowlist.",
            }
        return self._run_allowed_command(canonical_command)

    def inspect_card(self, command_key: str) -> dict[str, Any]:
        normalized_key = command_key.strip().lower()
        command = INSPECTION_COMMANDS.get(normalized_key)
        if command is None:
            return {
                "command_key": normalized_key,
                "command": "",
                "success": False,
                "exit_code": None,
                "output": "",
                "error": "Unsupported inspection command.",
            }
        return {
            "command_key": normalized_key,
            **self._run_allowed_command(command),
        }

    def _run_allowed_command(self, command: str) -> dict[str, Any]:
        if command not in SAFE_COMMANDS:
            return {
                "command": command,
                "success": False,
                "exit_code": None,
                "output": "",
                "error": "Command is not allowed.",
            }

        if not self.client_available:
            return {
                "command": command,
                "success": False,
                "exit_code": None,
                "output": "",
                "error": "Configured Proxmark client path was not found.",
            }

        args = self._build_client_command(command)
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "text": True,
            "errors": "replace",
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        with self._command_lock:
            with tempfile.TemporaryFile(
                mode="w+",
                encoding="utf-8",
                errors="replace",
            ) as output_file:
                popen_kwargs["stdout"] = output_file
                popen_kwargs["stderr"] = subprocess.STDOUT
                try:
                    process = subprocess.Popen(args, **popen_kwargs)
                    process.wait(timeout=self.timeout_seconds)
                    timed_out = False
                except subprocess.TimeoutExpired:
                    timed_out = True
                    self._cancel_timed_out_command(process)
                except OSError as exc:
                    return {
                        "command": command,
                        "success": False,
                        "exit_code": None,
                        "output": "",
                        "error": str(exc),
                    }
                finally:
                    if "process" in locals() and process.stdin is not None:
                        try:
                            process.stdin.close()
                        except (BrokenPipeError, OSError):
                            pass

                output_file.flush()
                output_file.seek(0)
                output = output_file.read().strip()
                output = redact_proxmark_output(output, command)

            if timed_out:
                return {
                    "command": command,
                    "success": False,
                    "exit_code": None,
                    "output": output,
                    "error": (
                        f"Command timed out after {self.timeout_seconds} seconds. "
                        "Wait for the device LEDs to settle before retrying."
                    ),
                }

        error = None
        if process.returncode != 0:
            error = self._describe_command_error(output)

        return {
            "command": command,
            "success": process.returncode == 0,
            "exit_code": _normalize_exit_code(process.returncode),
            "output": output,
            "error": error,
        }

    def _cancel_timed_out_command(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if process.stdin is not None:
                process.stdin.write("\n")
                process.stdin.flush()
            process.wait(timeout=3)
        except (BrokenPipeError, OSError, subprocess.TimeoutExpired):
            self._terminate_process_tree(process)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return

        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
                text=True,
            )
            return

        os.killpg(os.getpgid(process.pid), signal.SIGKILL)

    def _build_client_command(self, command: str) -> list[str] | str:
        client_args = [self.client_path, self.device_port, "-c", command]
        if Path(self.client_path).suffix.lower() not in {".bat", ".cmd"}:
            return client_args

        return f'cmd.exe /d /s /c "{subprocess.list2cmdline(client_args)}"'

    def _describe_command_error(self, output: str) -> str:
        normalized_output = output.lower()
        normalized_port = self.device_port or "the configured port"
        if "invalid serial port" in normalized_output:
            return (
                f"The Proxmark client could not open {normalized_port}. "
                "Close any existing Proxmark/Phosphor/pm3 window using the device, "
                "confirm the USB cable is connected, then retry."
            )
        if "cannot communicate with the proxmark3" in normalized_output:
            return (
                f"The Proxmark client opened {normalized_port}, but the device did not answer. "
                "Wait for any active search to finish and retry. If the previous search timed out, "
                "reconnect the USB cable once before the next assessment."
            )
        if "no data found" in normalized_output or "couldn't identify a chipset" in normalized_output:
            return "No matching card was identified by this read-only command."
        if "command execution time out" in normalized_output:
            return "The Proxmark command timed out while searching for a card."
        return "Proxmark client returned a non-zero exit code."


class BridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "PASS-PAC-ProxmarkBridge/0.1"

    def do_OPTIONS(self) -> None:
        self._send_json({})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok", "service": "PASS-PAC Proxmark Bridge"})
            return
        if self.path == "/status":
            self._send_json(self.server.bridge_state.status())
            return
        self._send_json({"error": "Not found."}, status=404)

    def do_POST(self) -> None:
        if self.path == "/probe":
            self._send_json(self.server.bridge_state.probe_hw_version())
            return
        if self.path == "/identify":
            payload = self._read_json()
            technology = str(payload.get("technology", ""))
            self._send_json(self.server.bridge_state.identify_card(technology))
            return
        if self.path == "/diagnostic":
            payload = self._read_json()
            diagnostic = str(payload.get("diagnostic", ""))
            self._send_json(self.server.bridge_state.run_diagnostic(diagnostic))
            return
        if self.path == "/command":
            payload = self._read_json()
            command = str(payload.get("command", ""))
            self._send_json(self.server.bridge_state.run_safe_command(command))
            return
        if self.path == "/inspect":
            payload = self._read_json()
            command_key = str(payload.get("command_key", ""))
            self._send_json(self.server.bridge_state.inspect_card(command_key))
            return
        self._send_json({"error": "Not found."}, status=404)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        if content_length <= 0:
            return {}
        try:
            raw_body = self.rfile.read(content_length).decode("utf-8")
            payload = json.loads(raw_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


class BridgeServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BridgeRequestHandler],
        bridge_state: BridgeState,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.bridge_state = bridge_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PASS-PAC Proxmark host bridge.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--client", required=True, help="Path to proxmark3.exe or pm3 client.")
    parser.add_argument("--device-port", required=True, help="Windows COM port, for example COM8.")
    parser.add_argument("--timeout", default=20, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state = BridgeState(
        client_path=args.client,
        device_port=args.device_port,
        timeout_seconds=max(1, args.timeout),
    )
    server = BridgeServer((args.host, args.port), BridgeRequestHandler, state)
    print(f"PASS-PAC Proxmark bridge listening on http://{args.host}:{args.port}")
    print(f"Client: {args.client}")
    print(f"Port: {args.device_port}")
    server.serve_forever()


def _normalize_exit_code(exit_code: int) -> int:
    if exit_code > 2_147_483_647:
        return exit_code - 4_294_967_296
    return exit_code


if __name__ == "__main__":
    main()
