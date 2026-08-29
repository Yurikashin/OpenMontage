"""Small governed client for the Polza Media API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


class PolzaError(RuntimeError):
    """A sanitized Polza transport or generation failure."""


@dataclass(frozen=True)
class PolzaGeneration:
    id: str
    status: str
    model: str | None = None
    output_url: str | None = None
    cost_rub: Decimal | None = None
    payload: dict[str, Any] | None = None


def _output_url(data: Any) -> str | None:
    if isinstance(data, str) and data.startswith(("http://", "https://")):
        return data
    if isinstance(data, dict):
        for key in ("url", "video_url", "image_url", "audio_url"):
            value = data.get(key)
            if isinstance(value, str):
                return value
        for key in ("video", "image", "audio", "output", "data"):
            value = _output_url(data.get(key))
            if value:
                return value
    if isinstance(data, list):
        for item in data:
            value = _output_url(item)
            if value:
                return value
    return None


def _generation(payload: dict[str, Any]) -> PolzaGeneration:
    usage = payload.get("usage") or {}
    raw_cost = usage.get("cost_rub", usage.get("cost"))
    return PolzaGeneration(
        id=str(payload.get("id") or payload.get("taskId") or payload.get("task_id") or ""),
        status=str(payload.get("status") or "pending"),
        model=payload.get("model"),
        output_url=_output_url(payload.get("data")),
        cost_rub=Decimal(str(raw_cost)) if raw_cost is not None else None,
        payload=payload,
    )


class PolzaClient:
    def __init__(
        self,
        api_key: str,
        *,
        session: Any | None = None,
        base_url: str = "https://polza.ai/api/v1",
        timeout_seconds: int = 60,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("Polza API key is required")
        if session is None:
            import requests

            session = requests.Session()
        self._api_key = api_key
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._sleep = sleep

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _safe_error(self, action: str, exc: Exception, response: Any | None = None) -> PolzaError:
        detail = None
        if response is not None:
            try:
                payload = response.json()
                error = payload.get("error") if isinstance(payload, dict) else None
                if isinstance(error, dict):
                    detail = error.get("message") or error.get("code")
                elif isinstance(error, str):
                    detail = error
                if not detail and isinstance(payload, dict):
                    detail = payload.get("message") or payload.get("detail")
            except Exception:
                detail = None
        message = str(exc)
        if detail:
            message = f"{message}: {detail}"
        message = message.replace(self._api_key, "<redacted>")
        return PolzaError(f"Polza {action} failed (credentials <redacted>): {message}")

    def get_model(self, model_id: str) -> dict[str, Any]:
        try:
            response = self._session.get(
                f"{self._base_url}/models",
                headers=self._headers,
                params={"include_providers": "true"},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise self._safe_error("model catalog request", exc) from exc

        for model in payload.get("data", payload.get("models", [])):
            if model.get("id") == model_id:
                return model
        raise PolzaError(f"Polza model not found: {model_id}")

    @staticmethod
    def _tier_matches(conditions: list[str], parameters: dict[str, Any]) -> bool:
        def normalized(value: Any) -> str:
            if isinstance(value, bool):
                return str(value).lower()
            return str(value)

        for condition in conditions:
            if "=" not in condition:
                return False
            name, expected = condition.split("=", 1)
            if normalized(parameters.get(name)) != expected:
                return False
        return True

    def estimate_rub(self, model_id: str, parameters: dict[str, Any]) -> Decimal:
        model = self.get_model(model_id)
        pricing = (model.get("top_provider") or {}).get("pricing") or model.get("pricing") or {}
        tiers = pricing.get("tiers") or []
        matches = [
            tier
            for tier in tiers
            if tier.get("conditions") and self._tier_matches(tier["conditions"], parameters)
        ]
        tier = matches[0] if matches else next(
            (candidate for candidate in tiers if not candidate.get("conditions")),
            None,
        )
        if not tier or tier.get("cost_rub") is None:
            raise PolzaError(f"Polza price is unavailable for model {model_id}")
        cost = Decimal(str(tier["cost_rub"]))
        if pricing.get("unitParam") == "duration":
            duration = Decimal(str(parameters.get("duration", 0)))
            if duration <= 0:
                raise PolzaError(f"Positive duration is required for model {model_id}")
            cost *= duration
        return cost

    def generate(self, model_id: str, input_payload: dict[str, Any]) -> PolzaGeneration:
        response = None
        try:
            response = self._session.post(
                f"{self._base_url}/media",
                headers=self._headers,
                json={"model": model_id, "input": input_payload, "async": True},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            result = _generation(response.json())
        except Exception as exc:
            raise self._safe_error("media request", exc, response) from exc
        if not result.id:
            raise PolzaError("Polza media request returned no generation id")
        return result

    def wait(
        self,
        generation_id: str,
        *,
        timeout_seconds: int = 900,
        poll_interval_seconds: float = 5,
    ) -> PolzaGeneration:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                response = self._session.get(
                    f"{self._base_url}/media/{generation_id}",
                    headers=self._headers,
                    timeout=self._timeout_seconds,
                )
                response.raise_for_status()
                result = _generation(response.json())
            except Exception as exc:
                raise self._safe_error("media status request", exc) from exc

            if result.status == "completed":
                if not result.output_url:
                    raise PolzaError("Polza completed generation returned no media URL")
                return result
            if result.status in {"failed", "cancelled", "expired"}:
                detail = (result.payload or {}).get("error") or result.status
                raise PolzaError(f"Polza generation {generation_id} failed: {detail}")
            self._sleep(poll_interval_seconds)
        raise PolzaError(f"Polza generation {generation_id} timed out")

    def download(self, url: str, output_path: str | Path) -> Path:
        output = Path(output_path)
        try:
            response = self._session.get(url, timeout=300, stream=True)
            response.raise_for_status()
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("wb") as handle:
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        handle.write(chunk)
        except Exception as exc:
            raise self._safe_error("media download", exc) from exc
        return output
