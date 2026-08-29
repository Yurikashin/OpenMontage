from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from lib.providers.polza import PolzaClient, PolzaError


MODEL_CATALOG = {
    "data": [
        {
            "id": "grok-imagine-video-1-5",
            "top_provider": {
                "pricing": {
                    "unitParam": "duration",
                    "currency": "RUB",
                    "tiers": [
                        {"conditions": [], "cost_rub": "3.03750000"},
                        {"conditions": ["resolution=480p"], "cost_rub": "1.62000000"},
                        {"conditions": ["resolution=720p"], "cost_rub": "3.03750000"},
                    ],
                }
            },
        },
        {
            "id": "black-forest-labs/flux.2-pro",
            "top_provider": {
                "pricing": {
                    "currency": "RUB",
                    "tiers": [
                        {"conditions": [], "cost_rub": "5.00000000"},
                        {"conditions": ["image_resolution=1K"], "cost_rub": "5.00000000"},
                        {"conditions": ["image_resolution=2K"], "cost_rub": "7.00000000"},
                    ],
                }
            },
        },
        {
            "id": "bytedance/seedance-2-mini",
            "top_provider": {
                "pricing": {
                    "unitParam": "duration",
                    "currency": "RUB",
                    "tiers": [
                        {"conditions": [], "cost_rub": "6.75000000"},
                        {
                            "conditions": ["resolution=720p", "has_video=false"],
                            "cost_rub": "5.53500000",
                        },
                    ],
                }
            },
        },
    ]
}


class FakeResponse:
    def __init__(self, payload=None, *, content: bytes = b"", status_code: int = 200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    @property
    def text(self):
        if isinstance(self._payload, dict):
            import json

            return json.dumps(self._payload)
        return self.content.decode("utf-8", errors="replace")

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=64 * 1024):
        del chunk_size
        yield self.content


class FakeSession:
    def __init__(self, *, gets=None, posts=None):
        self.gets = list(gets or [])
        self.posts = list(posts or [])
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.gets.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.posts.pop(0)


def test_catalog_request_uses_bearer_auth_and_returns_requested_model():
    session = FakeSession(gets=[FakeResponse(MODEL_CATALOG)])
    client = PolzaClient("secret-token", session=session)

    model = client.get_model("grok-imagine-video-1-5")

    assert model["id"] == "grok-imagine-video-1-5"
    method, url, kwargs = session.calls[0]
    assert method == "GET"
    assert url == "https://polza.ai/api/v1/models"
    assert kwargs["params"] == {"include_providers": "true"}
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"


@pytest.mark.parametrize(
    ("model_id", "parameters", "expected"),
    [
        ("grok-imagine-video-1-5", {"resolution": "480p", "duration": 6}, Decimal("9.72")),
        ("grok-imagine-video-1-5", {"resolution": "720p", "duration": 6}, Decimal("18.225")),
        ("black-forest-labs/flux.2-pro", {"image_resolution": "1K"}, Decimal("5")),
        ("black-forest-labs/flux.2-pro", {"image_resolution": "2K"}, Decimal("7")),
        (
            "bytedance/seedance-2-mini",
            {"resolution": "720p", "has_video": False, "duration": 4},
            Decimal("22.14000000"),
        ),
    ],
)
def test_estimate_rub_selects_matching_tier_and_applies_duration(model_id, parameters, expected):
    client = PolzaClient("secret", session=FakeSession(gets=[FakeResponse(MODEL_CATALOG)]))

    assert client.estimate_rub(model_id, parameters) == expected


def test_generate_posts_async_media_request_and_returns_generation():
    session = FakeSession(
        posts=[
            FakeResponse(
                {
                    "id": "gen-123",
                    "status": "pending",
                    "model": "grok-imagine-video-1-5",
                }
            )
        ]
    )
    client = PolzaClient("secret", session=session)

    generation = client.generate(
        "grok-imagine-video-1-5",
        {"prompt": "bright group play", "duration": 3, "resolution": "720p"},
    )

    assert generation.id == "gen-123"
    assert generation.status == "pending"
    method, url, kwargs = session.calls[0]
    assert method == "POST"
    assert url == "https://polza.ai/api/v1/media"
    assert kwargs["json"] == {
        "model": "grok-imagine-video-1-5",
        "input": {"prompt": "bright group play", "duration": 3, "resolution": "720p"},
        "async": True,
    }


def test_wait_returns_completed_generation_with_actual_rub_cost():
    session = FakeSession(
        gets=[
            FakeResponse({"id": "gen-123", "status": "processing"}),
            FakeResponse(
                {
                    "id": "gen-123",
                    "status": "completed",
                    "data": {"url": "https://cdn.example/video.mp4"},
                    "usage": {"cost_rub": "9.72"},
                }
            ),
        ]
    )
    client = PolzaClient("secret", session=session, sleep=lambda _: None)

    result = client.wait("gen-123", timeout_seconds=10, poll_interval_seconds=0)

    assert result.status == "completed"
    assert result.output_url == "https://cdn.example/video.mp4"
    assert result.cost_rub == Decimal("9.72")


def test_download_streams_binary_output(tmp_path: Path):
    session = FakeSession(gets=[FakeResponse(content=b"media-bytes")])
    client = PolzaClient("secret", session=session)
    output = tmp_path / "clip.mp4"

    client.download("https://cdn.example/clip.mp4", output)

    assert output.read_bytes() == b"media-bytes"


def test_errors_never_expose_api_key():
    token = "pza_super_secret"
    session = FakeSession(gets=[FakeResponse(status_code=401)])
    client = PolzaClient(token, session=session)

    with pytest.raises(PolzaError) as error:
        client.get_model("missing")

    assert token not in str(error.value)
    assert "<redacted>" in str(error.value)


def test_media_error_includes_sanitized_response_detail():
    token = "pza_super_secret"
    session = FakeSession(
        posts=[
            FakeResponse(
                {"error": {"message": f"bad duration for {token}"}},
                status_code=400,
            )
        ]
    )
    client = PolzaClient(token, session=session)

    with pytest.raises(PolzaError) as error:
        client.generate("grok-imagine-video-1-5", {"duration": 3})

    assert "bad duration" in str(error.value)
    assert token not in str(error.value)
