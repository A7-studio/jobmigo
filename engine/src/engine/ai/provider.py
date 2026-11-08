"""The one interface every model adapter implements."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AiRequest:
    model: str
    system: str
    user: str
    timeout_s: float | None = None


@dataclass(frozen=True)
class AiResponse:
    text: str
    tokens_in: int
    tokens_out: int


class AiProvider(Protocol):
    """One model call. Adapters raise `AiUnavailableError` when the call fails."""

    name: str

    async def complete(self, request: AiRequest) -> AiResponse: ...
