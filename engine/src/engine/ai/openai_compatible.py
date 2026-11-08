"""An adapter for any OpenAI-compatible chat-completions API, using plain httpx.

Retries once on a timeout, network error, 429 or 5xx. Never logs prompts, replies,
headers or keys: only the provider, status and duration.
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from engine.ai.errors import AiUnavailableError
from engine.ai.provider import AiRequest, AiResponse

log = logging.getLogger("engine")

DEFAULT_TIMEOUT_S = 60.0


@dataclass(frozen=True)
class _Failed:
    status: int | str
    transient: bool


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return 0
    if not math.isfinite(value) or value < 0:
        return 0
    return int(value)


class OpenAiCompatibleProvider:
    def __init__(
        self,
        *,
        name: str,
        url: str,
        api_key: str,
        json_mode: bool,
        client: httpx.AsyncClient | None = None,
        retry_delay_s: float = 0.5,
    ) -> None:
        self.name = name
        self._url = url
        self._api_key = api_key
        self._json_mode = json_mode
        self._client = client
        self._retry_delay_s = retry_delay_s

    async def complete(self, request: AiRequest) -> AiResponse:
        started = time.monotonic()
        for attempt in (1, 2):
            outcome = await self._attempt(request)
            if isinstance(outcome, AiResponse):
                return outcome
            log.warning(
                "ai provider call failed",
                extra={
                    "provider": self.name,
                    "status": outcome.status,
                    "attempt": attempt,
                    "durationMs": round((time.monotonic() - started) * 1000),
                },
            )
            if not outcome.transient or attempt == 2:
                break
            await asyncio.sleep(self._retry_delay_s)
        raise AiUnavailableError

    async def _attempt(self, request: AiRequest) -> AiResponse | _Failed:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
        }
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}

        limit = (
            request.timeout_s if request.timeout_s is not None else DEFAULT_TIMEOUT_S
        )
        client = self._client or httpx.AsyncClient()
        try:
            # httpx timeouts apply per phase; the total limit is enforced here.
            async with asyncio.timeout(limit):
                response = await client.post(
                    self._url,
                    json=body,
                    headers={"authorization": f"Bearer {self._api_key}"},
                )
        except (httpx.HTTPError, TimeoutError):
            return _Failed("network", True)
        finally:
            if self._client is None:
                await client.aclose()

        if not response.is_success:
            status = response.status_code
            return _Failed(status, status == 429 or status >= 500)

        try:
            payload = response.json()
        except ValueError:
            return _Failed(response.status_code, False)
        if not isinstance(payload, dict):
            return _Failed(response.status_code, False)

        # A reply with no text (a refusal, a cutoff) is still billed. Return empty
        # text with the tokens so the gateway records the usage and rejects the
        # reply as invalid, instead of losing the spend.
        choices = payload.get("choices")
        content: object = None
        has_message = False
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            message = choices[0].get("message")
            if isinstance(message, dict):
                has_message = True
                content = message.get("content")
        if payload.get("error") and not has_message:
            # Some gateways answer HTTP 200 with an error body: that is "unavailable",
            # not an invalid answer, and nothing was billed.
            return _Failed(response.status_code, False)
        if isinstance(content, list):
            # Some gateways return content as a list of parts; join the text parts.
            content = "".join(
                part["text"]
                for part in content
                if isinstance(part, dict)
                and part.get("type") == "text"
                and isinstance(part.get("text"), str)
            )
        usage = payload.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        return AiResponse(
            text=content if isinstance(content, str) else "",
            tokens_in=_count(usage.get("prompt_tokens")),
            tokens_out=_count(usage.get("completion_tokens")),
        )
