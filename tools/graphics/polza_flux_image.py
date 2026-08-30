"""Flux-2 Pro image generation through the Polza Media API."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from lib.providers.polza import PolzaClient
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


MODEL_ID = "black-forest-labs/flux.2-pro"


def _media_ref(value: str) -> dict[str, str]:
    if value.startswith(("http://", "https://", "data:")):
        return {"type": "url" if value.startswith("http") else "base64", "data": value}
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(f"Reference image not found: {path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "base64", "data": f"data:{mime_type};base64,{encoded}"}


def _rub_to_usd(value: float) -> float:
    rate = float(os.environ.get("POLZA_RUB_PER_USD", "100"))
    return value / rate if rate > 0 else 0.0


class PolzaFluxImage(BaseTool):
    name = "polza_flux_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "polza"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "Set POLZA_API_KEY to a dedicated Polza API key."
    agent_skills = ["flux-best-practices", "bfl-api"]
    capabilities = ["generate_image", "text_to_image", "reference_to_image"]
    supports = {
        "reference_image": True,
        "multiple_reference_images": True,
        "custom_size": False,
        "seed": False,
    }
    best_for = [
        "high-quality vertical B-roll keyframes",
        "reference-aware support images",
        "Russian-ruble budgeted generation through one account",
    ]
    not_good_for = ["rendering Russian text inside images", "documented real-event proof"]
    fallback_tools = ["flux_image", "seedream_image", "recraft_image"]
    quality_score = 0.9

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "maxLength": 5000},
            "model": {"type": "string", "enum": [MODEL_ID], "default": MODEL_ID},
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                "default": "9:16",
            },
            "image_resolution": {"type": "string", "enum": ["1K", "2K"], "default": "1K"},
            "reference_images": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "output_path": {"type": "string"},
            "max_cost_rub": {"type": "number", "exclusiveMinimum": 0},
            "timeout_seconds": {"type": "integer", "minimum": 30, "default": 900},
            "poll_interval_seconds": {"type": "number", "minimum": 1, "default": 5},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "image_resolution"]
    side_effects = ["writes image file to output_path", "calls paid Polza Media API"]
    user_visible_verification = ["Inspect image for semantic match, faces, hands, and realism"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if os.environ.get("POLZA_API_KEY") else ToolStatus.UNAVAILABLE

    def estimate_cost_rub(self, inputs: dict[str, Any]) -> float:
        return 7.0 if inputs.get("image_resolution", "1K") == "2K" else 5.0

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return _rub_to_usd(self.estimate_cost_rub(inputs))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("POLZA_API_KEY")
        if not api_key:
            return ToolResult(success=False, error=self.install_instructions)

        started = time.time()
        model = inputs.get("model", MODEL_ID)
        payload = {
            "prompt": inputs["prompt"],
            "aspect_ratio": inputs.get("aspect_ratio", "9:16"),
            "image_resolution": inputs.get("image_resolution", "1K"),
            "images": [_media_ref(value) for value in inputs.get("reference_images", [])],
        }
        output_path = Path(inputs.get("output_path", "polza-flux-output.png"))

        try:
            client = PolzaClient(api_key)
            estimate = client.estimate_rub(model, payload)
            max_cost = inputs.get("max_cost_rub")
            if max_cost is not None and estimate > Decimal(str(max_cost)):
                raise ValueError(
                    f"live estimate {estimate} RUB exceeds max_cost_rub {max_cost} RUB"
                )
            pending = client.generate(model, payload)
            completed = client.wait(
                pending.id,
                timeout_seconds=int(inputs.get("timeout_seconds", 900)),
                poll_interval_seconds=float(inputs.get("poll_interval_seconds", 5)),
            )
            client.download(completed.output_url or "", output_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"Polza Flux generation failed: {exc}")

        actual = float(completed.cost_rub if completed.cost_rub is not None else estimate)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "request_id": pending.id,
                "prompt": inputs["prompt"],
                "aspect_ratio": payload["aspect_ratio"],
                "image_resolution": payload["image_resolution"],
                "output": str(output_path),
                "output_path": str(output_path),
                "estimated_cost_rub": float(estimate),
                "cost_rub": actual,
            },
            artifacts=[str(output_path)],
            cost_usd=_rub_to_usd(actual),
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )
