"""Current fal.ai pricing and request controls for paid video providers."""

from __future__ import annotations

import pytest

from tools.video.kling_video import KlingVideo
from tools.video.seedance_video import SeedanceVideo
from tools.video.video_selector import VideoSelector


def test_kling_v3_standard_cost_depends_on_duration_and_audio() -> None:
    tool = KlingVideo()

    assert tool.estimate_cost(
        {"duration": "10", "generate_audio": False}
    ) == pytest.approx(0.84)
    assert tool.estimate_cost(
        {"duration": "10", "generate_audio": True}
    ) == pytest.approx(1.26)
    assert tool.estimate_cost({"duration": "5"}) == pytest.approx(0.63)


def test_kling_v3_exposes_multi_shot_and_audio_controls() -> None:
    properties = KlingVideo.input_schema["properties"]

    assert "multi_prompt" in properties
    assert properties["shot_type"]["enum"] == ["customize", "intelligent"]
    assert properties["generate_audio"]["default"] is True
    assert properties["multi_prompt"]["items"]["properties"]["prompt"]["maxLength"] == 512
    assert (
        VideoSelector.input_schema["properties"]["generate_audio"]["type"]
        == "boolean"
    )


def test_kling_v3_rejects_oversized_shot_prompt_before_api_call() -> None:
    result = KlingVideo().execute(
        {
            "multi_prompt": [{"prompt": "x" * 513, "duration": "5"}],
            "duration": "5",
        }
    )

    assert not result.success
    assert "invalid shots: [1]" in (result.error or "")


def test_seedance_25_uses_token_pricing_for_resolution_and_aspect_ratio() -> None:
    tool = SeedanceVideo()

    assert tool.estimate_cost(
        {
            "model_version": "2.5",
            "duration": "10",
            "resolution": "720p",
            "aspect_ratio": "9:16",
        }
    ) == pytest.approx(4.62)
    assert tool.estimate_cost(
        {
            "model_version": "2.5",
            "duration": "10",
            "resolution": "480p",
            "aspect_ratio": "9:16",
        }
    ) == pytest.approx(2.15)
    assert tool.estimate_cost(
        {
            "model_version": "2.5",
            "duration": "10",
            "resolution": "720p",
            "aspect_ratio": "21:9",
        }
    ) == pytest.approx(4.64)


def test_seedance_20_rates_are_unchanged() -> None:
    tool = SeedanceVideo()

    assert tool.estimate_cost(
        {"model_version": "2.0", "duration": "10"}
    ) == pytest.approx(3.03)
    assert tool.estimate_cost(
        {"model_version": "2.0", "model_variant": "fast", "duration": "10"}
    ) == pytest.approx(2.42)
