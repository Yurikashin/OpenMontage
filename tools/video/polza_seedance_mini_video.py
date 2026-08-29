"""Seedance 2 Mini video generation through the Polza Media API."""

from __future__ import annotations

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


MODEL_ID = "bytedance/seedance-2-mini"


def _rub_to_usd(value: float) -> float:
    rate = float(os.environ.get("POLZA_RUB_PER_USD", "100"))
    return value / rate if rate > 0 else 0.0


class PolzaSeedanceMiniVideo(BaseTool):
    name = "polza_seedance_mini_video"
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
    agent_skills = ["ai-video-gen"]
    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "native_audio": True,
        "cinematic_quality": True,
    }
    best_for = [
        "documented short vertical B-roll through Polza",
        "budgeted 480p or 720p motion inserts",
        "fallback when an approved preview model rejects a request before generation",
    ]
    not_good_for = ["documented real-event proof", "Russian text rendered inside video"]
    fallback_tools = []
    quality_score = 0.86

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "maxLength": 20000},
            "model": {"type": "string", "enum": [MODEL_ID], "default": MODEL_ID},
            "duration": {"type": "integer", "minimum": 4, "maximum": 15, "default": 4},
            "resolution": {"type": "string", "enum": ["480p", "720p"], "default": "720p"},
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "auto"],
                "default": "9:16",
            },
            "generate_audio": {"type": "boolean", "default": False},
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

    @staticmethod
    def estimate_cost_rub(inputs: dict[str, Any]) -> float:
        per_second = 2.565 if inputs.get("resolution", "720p") == "480p" else 5.535
        return per_second * int(inputs.get("duration", 4))

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return _rub_to_usd(self.estimate_cost_rub(inputs))

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("POLZA_API_KEY")
        if not api_key:
            return ToolResult(success=False, error=self.install_instructions)

        started = time.time()
        model = inputs.get("model", MODEL_ID)
        duration = int(inputs.get("duration", 4))
        resolution = inputs.get("resolution", "720p")
        payload = {
            "prompt": inputs["prompt"],
            "duration": str(duration),
            "resolution": resolution,
            "aspect_ratio": inputs.get("aspect_ratio", "9:16"),
            "images": [],
            "videos": [],
            "generate_audio": "true" if inputs.get("generate_audio", False) else "false",
        }
        output_path = Path(inputs.get("output_path", "polza-seedance-mini-output.mp4"))

        try:
            client = PolzaClient(api_key)
            estimate = client.estimate_rub(
                model,
                {"duration": duration, "resolution": resolution, "has_video": False},
            )
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
            return ToolResult(success=False, error=f"Polza Seedance generation failed: {exc}")

        actual = float(completed.cost_rub if completed.cost_rub is not None else estimate)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "request_id": pending.id,
                "prompt": inputs["prompt"],
                "duration": duration,
                "resolution": resolution,
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
