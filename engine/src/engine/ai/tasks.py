"""What a model task is: a name, a tier, a versioned prompt and typed input/output."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from engine.ai.config import Tier

Workflow = Literal["parse", "screen", "evaluate", "tailor", "reach_check", "outreach"]


@dataclass(frozen=True)
class AiTask[I: BaseModel, O: BaseModel]:
    """A model task.

    The task name picks the tier (and so the model) through configuration. The prompt
    `version` must change whenever the prompt text does, because it is recorded in
    the ledger and is part of the cache key.
    """

    name: str
    workflow: Workflow
    tier: Tier
    prompt_version: str
    system: str
    user: Callable[[I], str]
    input_model: type[I]
    output_model: type[O]
    # Reuse cached results for identical input.
    cache: bool = True
    # Per-call time limit in seconds; the adapter defaults to 60 when unset.
    timeout_s: float | None = None
