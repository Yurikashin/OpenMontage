from __future__ import annotations

from decimal import Decimal

import pytest

from lib.providers.polza import PolzaGeneration
from tools.base_tool import ToolStatus


class FakePolzaClient:
    instances = []
    estimate = Decimal("5")
    completed = PolzaGeneration(
        id="gen-1",
        status="completed",
        model="test-model",
        output_url="https://cdn.example/output.bin",
        cost_rub=Decimal("4.75"),
    )

    def __init__(self, api_key):
        self.api_key = api_key
        self.generated = []
        self.downloaded = []
        self.__class__.instances.append(self)

    def estimate_rub(self, model_id, parameters):
        self.estimated = (model_id, parameters)
        return self.__class__.estimate

    def generate(self, model_id, payload):
        self.generated.append((model_id, payload))
        return PolzaGeneration(id="gen-1", status="pending", model=model_id)

    def wait(self, generation_id, **kwargs):
        self.waited = (generation_id, kwargs)
        return self.__class__.completed

    def download(self, url, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"generated")
        self.downloaded.append((url, output_path))
        return output_path


@pytest.fixture(autouse=True)
def reset_fake_client():
    FakePolzaClient.instances.clear()
    FakePolzaClient.estimate = Decimal("5")
    FakePolzaClient.completed = PolzaGeneration(
        id="gen-1",
        status="completed",
        model="test-model",
        output_url="https://cdn.example/output.bin",
        cost_rub=Decimal("4.75"),
    )


def test_polza_tools_require_their_own_environment_key(monkeypatch):
    from tools.graphics.polza_flux_image import PolzaFluxImage
    from tools.video.polza_grok_video import PolzaGrokVideo

    monkeypatch.delenv("POLZA_API_KEY", raising=False)
    assert PolzaFluxImage().get_status() == ToolStatus.UNAVAILABLE
    assert PolzaGrokVideo().get_status() == ToolStatus.UNAVAILABLE

    monkeypatch.setenv("POLZA_API_KEY", "placeholder")
    assert PolzaFluxImage().get_status() == ToolStatus.AVAILABLE
    assert PolzaGrokVideo().get_status() == ToolStatus.AVAILABLE


@pytest.mark.parametrize(("resolution", "expected"), [("1K", 5.0), ("2K", 7.0)])
def test_flux_fallback_rub_estimate_is_resolution_aware(resolution, expected):
    from tools.graphics.polza_flux_image import PolzaFluxImage

    assert PolzaFluxImage().estimate_cost_rub({"image_resolution": resolution}) == expected


@pytest.mark.parametrize(("resolution", "expected"), [("480p", 9.72), ("720p", 18.225)])
def test_grok_fallback_rub_estimate_is_duration_aware(resolution, expected):
    from tools.video.polza_grok_video import PolzaGrokVideo

    assert PolzaGrokVideo().estimate_cost_rub({"resolution": resolution, "duration": 6}) == expected


def test_flux_executes_exact_model_and_records_actual_rub(monkeypatch, tmp_path):
    import tools.graphics.polza_flux_image as module

    monkeypatch.setenv("POLZA_API_KEY", "placeholder")
    monkeypatch.setattr(module, "PolzaClient", FakePolzaClient)
    output = tmp_path / "frame.png"

    result = module.PolzaFluxImage().execute(
        {
            "prompt": "bright orange art materials in a kindergarten",
            "aspect_ratio": "9:16",
            "image_resolution": "1K",
            "output_path": str(output),
        }
    )

    assert result.success is True
    assert result.artifacts == [str(output)]
    assert result.data["cost_rub"] == 4.75
    assert result.data["estimated_cost_rub"] == 5.0
    assert result.data["request_id"] == "gen-1"
    client = FakePolzaClient.instances[-1]
    assert client.generated == [
        (
            "black-forest-labs/flux.2-pro",
            {
                "prompt": "bright orange art materials in a kindergarten",
                "aspect_ratio": "9:16",
                "image_resolution": "1K",
                "images": [],
            },
        )
    ]


def test_grok_executes_approved_720p_clip_without_retry(monkeypatch, tmp_path):
    import tools.video.polza_grok_video as module
    import tools.video._shared as shared

    monkeypatch.setenv("POLZA_API_KEY", "placeholder")
    monkeypatch.setattr(module, "PolzaClient", FakePolzaClient)
    monkeypatch.setattr(shared, "probe_output", lambda path: {"width": 720, "height": 1280})
    FakePolzaClient.estimate = Decimal("9.1125")
    output = tmp_path / "clip.mp4"

    tool = module.PolzaGrokVideo()
    result = tool.execute(
        {
            "prompt": "children's hands pass bright paper shapes across a table",
            "duration": 3,
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "output_path": str(output),
        }
    )

    assert tool.retry_policy.max_retries == 0
    assert result.success is True
    assert result.data["estimated_cost_rub"] == 9.1125
    assert result.data["cost_rub"] == 4.75
    assert result.data["duration"] == 3
    assert result.data["resolution"] == "720p"
    assert result.data["width"] == 720
    client = FakePolzaClient.instances[-1]
    assert len(client.generated) == 1
    assert client.generated[0] == (
        "grok-imagine-video-1-5",
        {
            "prompt": "children's hands pass bright paper shapes across a table",
            "duration": 3,
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "images": [],
        },
    )


def test_registry_discovers_polza_image_and_video_tools(monkeypatch):
    from tools.tool_registry import ToolRegistry

    monkeypatch.setenv("POLZA_API_KEY", "placeholder")
    registry = ToolRegistry()
    registry.discover()

    assert registry.get("polza_flux_image").provider == "polza"
    assert registry.get("polza_grok_video").provider == "polza"
