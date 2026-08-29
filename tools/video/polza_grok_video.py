"""Grok Imagine Video generation through the Polza Media API."""

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


MODEL_ID = "grok-imagine-video-1-5"


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


class PolzaGrokVideo(BaseTool):
    name = "polza_grok_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "polza"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = "Set POLZA_API_KEY to a dedicated Polza API key."
    agent_skills = ["grok-media", "ai-video-gen"]
    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "multiple_reference_images": True,
        "native_audio": False,
        "cinematic_quality": True,
    }
    best_for = [
        "short vertical B-roll with controlled RUB pricing",
        "image-conditioned motion from an approved keyframe",
        "bright dynamic social-video inserts",
    ]
    not_good_for = ["documented real-event proof", "Russian text rendered inside video"]
    fallback_tools = ["kling_video", "seedance_video", "veo_video"]
    quality_score = 0.88

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "maxLength": 4096},
            "model": {"type": "string", "enum": [MODEL_ID], "default": MODEL_ID},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video"],
                "default": "text_to_video",
            },
            "duration": {"type": "integer", "minimum": 1, "maximum": 15, "default": 3},
            "resolution": {"type": "string", "enum": ["480p", "720p"], "default": "720p"},
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "9:16", "3:2", "2:3", "auto"],
                "default": "9:16",
            },
            "reference_images": {"type": "array", "items": {"type": "string"}, "maxItems": 7},
            "output_path": {"type": "string"},
            "max_cost_rub": {"type": "number", "exclusiveMinimum": 0},
            "timeout_seconds": {"type": "integer", "minimum": 30, "default": 900},
            "poll_interval_seconds": {"type": "number", "minimum": 1, "default": 5},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["prompt", "model", "duration", "resolution", "aspect_ratio"]
    side_effects = ["writes video file to output_path", "calls paid Polza Media API"]
    user_visible_verification = ["Watch clip for motion, semantic match, faces, hands, and artifacts"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if os.environ.get("POLZA_API_KEY") else ToolStatus.UNAVAILABLE

    def estimate_cost_rub(self, inputs: dict[str, Any]) -> float:
        per_second = 1.62 if inputs.get("resolution", "720p") == "480p" else 3.0375
        return per_second * int(inputs.get("duration", 3))

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
            "duration": int(inputs.get("duration", 3)),
            "resolution": inputs.get("resolution", "720p"),
            "aspect_ratio": inputs.get("aspect_ratio", "9:16"),
            "images": [_media_ref(value) for value in inputs.get("reference_images", [])],
        }
        output_path = Path(inputs.get("output_path", "polza-grok-output.mp4"))

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
            from tools.video._shared import probe_output

            probed = probe_output(output_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"Polza Grok generation failed: {exc}")

        actual = float(completed.cost_rub if completed.cost_rub is not None else estimate)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "request_id": pending.id,
                "prompt": inputs["prompt"],
                "duration": payload["duration"],
                "resolution": payload["resolution"],
                "aspect_ratio": payload["aspect_ratio"],
                "output": str(output_path),
                "output_path": str(output_path),
                "estimated_cost_rub": float(estimate),
                "cost_rub": actual,
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=_rub_to_usd(actual),
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )
