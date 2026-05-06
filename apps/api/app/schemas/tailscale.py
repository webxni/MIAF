from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class TailscaleSettingsOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    tailscale_enabled: bool
    tailscale_mode: str
    tailscale_target_url: str
    tailscale_hostname: str | None
    tailscale_tailnet_url: str | None
    tailscale_last_status: str | None
    tailscale_last_checked_at: datetime | None
    tailscale_setup_completed: bool
    tailscale_notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TailscaleSettingsUpdate(BaseModel):
    tailscale_enabled: bool | None = None
    tailscale_mode: Literal["off", "direct_ip", "serve"] | None = None
    tailscale_target_url: str | None = Field(default=None, max_length=200)
    tailscale_hostname: str | None = Field(default=None, max_length=253)
    tailscale_tailnet_url: str | None = Field(default=None, max_length=500)
    tailscale_setup_completed: bool | None = None
    tailscale_notes: str | None = Field(default=None, max_length=1000)


class TailscaleLiveStatusOut(BaseModel):
    settings: TailscaleSettingsOut
    binary_available: bool
    tailscale_ip: str | None
    hostname: str | None
    serve_status: str | None
    private_url: str | None
    warnings: list[str]
    instructions_only: bool
    manual_commands: dict[str, str]
    setup_instructions: list[str]
