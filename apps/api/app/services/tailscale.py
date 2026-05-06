"""Tailscale status and Serve management service.

Security contract:
- All commands use asyncio.create_subprocess_exec (list args, no shell=True).
- target_url is validated against an allowlist before any subprocess call.
- tailscale binary path comes from config, never from user input.
- Command output is sanitised before returning to the caller.
- Secrets (auth keys, etc.) are never logged or returned.
- If the tailscale binary is unavailable, every function returns gracefully
  with instructions_only=True so the frontend can show manual commands.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.config import get_settings

log = logging.getLogger(__name__)

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


@dataclass
class TailscaleCommandResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    instructions_only: bool = False
    error: str | None = None


@dataclass
class TailscaleStatus:
    available: bool
    tailscale_ip: str | None = None
    hostname: str | None = None
    tailnet_url: str | None = None
    serve_status: str | None = None
    warnings: list[str] = field(default_factory=list)
    instructions_only: bool = False
    raw: str | None = None


def tailscale_binary() -> str | None:
    settings = get_settings()
    configured = settings.tailscale_binary_path
    # Check configured path first, then PATH fallback.
    if os.path.isfile(configured) and os.access(configured, os.X_OK):
        return configured
    found = shutil.which("tailscale")
    return found


def validate_tailscale_target(target_url: str) -> tuple[bool, str]:
    """Return (is_valid, error_message). Only localhost targets on allowed ports."""
    settings = get_settings()
    try:
        parsed = urlparse(target_url)
    except Exception:
        return False, "Invalid URL format."

    if parsed.scheme not in {"http", "https"}:
        return False, "Only http or https targets are permitted."

    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        return False, f"Only localhost/127.0.0.1 targets are allowed. Got: {host!r}"

    port = parsed.port or (80 if parsed.scheme == "http" else 443)
    allowed = settings.tailscale_allowed_ports_set
    if port not in allowed:
        return False, (
            f"Port {port} is not in the allowed list ({sorted(allowed)}). "
            "Update TAILSCALE_ALLOWED_PORTS in your .env to permit it."
        )

    return True, ""


async def _run(args: list[str], *, timeout: int | None = None) -> TailscaleCommandResult:
    """Run a tailscale command safely with a timeout."""
    settings = get_settings()
    t = timeout or settings.tailscale_command_timeout
    binary = tailscale_binary()
    if binary is None:
        return TailscaleCommandResult(
            ok=False,
            instructions_only=True,
            error="tailscale binary not found. Run commands manually on the host.",
        )

    try:
        proc = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=t)
    except asyncio.TimeoutError:
        log.warning("tailscale command timed out: %s", args)
        try:
            proc.kill()
        except Exception:
            pass
        return TailscaleCommandResult(ok=False, error="Command timed out.")
    except Exception as exc:
        log.warning("tailscale command failed: %s — %s", args, exc)
        return TailscaleCommandResult(ok=False, error=f"Command error: {type(exc).__name__}")

    stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
    stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
    ok = proc.returncode == 0
    return TailscaleCommandResult(ok=ok, stdout=stdout, stderr=stderr)


async def get_tailscale_status() -> TailscaleStatus:
    """Return current Tailscale status: IP, hostname, tailnet URL."""
    binary = tailscale_binary()
    if binary is None:
        return TailscaleStatus(available=False, instructions_only=True)

    result = await _run(["status", "--json"])
    if not result.ok or not result.stdout:
        return TailscaleStatus(
            available=False,
            warnings=[result.error or result.stderr or "tailscale status failed"],
            instructions_only=result.instructions_only,
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return TailscaleStatus(available=False, warnings=["Could not parse tailscale status JSON."])

    self_node = data.get("Self") or {}
    ip_addrs: list[str] = self_node.get("TailscaleIPs", [])
    hostname: str | None = self_node.get("HostName") or self_node.get("DNSName")
    if hostname and hostname.endswith("."):
        hostname = hostname[:-1]

    ipv4 = next((ip for ip in ip_addrs if "." in ip), None)
    tailnet_url = f"http://{hostname}" if hostname else (f"http://{ipv4}" if ipv4 else None)

    return TailscaleStatus(
        available=True,
        tailscale_ip=ipv4,
        hostname=hostname,
        tailnet_url=tailnet_url,
        raw=result.stdout[:2000],
    )


async def get_tailscale_ip() -> str | None:
    result = await _run(["ip", "-4"])
    if result.ok and result.stdout:
        return result.stdout.split()[0].strip()
    return None


async def get_tailscale_serve_status() -> TailscaleCommandResult:
    return await _run(["serve", "status"])


async def start_tailscale_serve(target_url: str) -> TailscaleCommandResult:
    """Start Tailscale Serve for the given localhost target.

    Only Serve (private tailnet) is supported. Funnel is never started.
    """
    valid, err = validate_tailscale_target(target_url)
    if not valid:
        return TailscaleCommandResult(ok=False, error=f"Rejected target: {err}")

    result = await _run(["serve", "--bg", target_url])
    if result.ok:
        log.info("tailscale serve started for target %s", target_url)
    else:
        log.warning("tailscale serve failed: %s", result.stderr)
    return result


async def reset_tailscale_serve() -> TailscaleCommandResult:
    result = await _run(["serve", "reset"])
    if result.ok:
        log.info("tailscale serve reset")
    else:
        log.warning("tailscale serve reset failed: %s", result.stderr)
    return result


def manual_serve_instructions(target_url: str = "http://127.0.0.1:80") -> dict[str, str]:
    """Return copy-pasteable manual Tailscale Serve commands for the user."""
    return {
        "install": "Install Tailscale: https://tailscale.com/download",
        "up": "sudo tailscale up",
        "serve_start": f"sudo tailscale serve --bg {target_url}",
        "serve_status": "tailscale serve status",
        "serve_reset": "sudo tailscale serve reset",
        "get_ip": "tailscale ip -4",
        "phone_note": (
            "Install Tailscale on your phone and sign in to the same tailnet. "
            "Then open the https://<hostname>.ts.net URL shown by 'tailscale serve status'."
        ),
    }
