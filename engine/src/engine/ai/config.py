"""Which model answers a task, where to reach it, and what a call costs.

Everything is read from the environment at call time, so a missing setting fails
the call with a clear message instead of stopping the engine from starting.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import TYPE_CHECKING, Literal

from engine.ai.errors import AiNotConfiguredError

if TYPE_CHECKING:
    import httpx

    from engine.ai.openai_compatible import OpenAiCompatibleProvider

Tier = Literal["cheap", "strong"]
Env = Mapping[str, str | None]


@dataclass(frozen=True)
class ProviderInfo:
    """A provider's chat-completions endpoint, from its public documentation."""

    url: str
    key_env: str
    # Only providers whose docs describe `response_format: json_object`.
    json_mode: bool


# Confirmed against each provider's public docs when this was written: DeepSeek
# documents api.deepseek.com/chat/completions and JSON output mode; Moonshot
# documents api.moonshot.ai/v1/chat/completions and OpenRouter openrouter.ai/api/v1,
# neither of which describes `response_format` there.
PROVIDERS: dict[str, ProviderInfo] = {
    "deepseek": ProviderInfo(
        "https://api.deepseek.com/chat/completions", "DEEPSEEK_API_KEY", True
    ),
    "moonshot": ProviderInfo(
        "https://api.moonshot.ai/v1/chat/completions", "MOONSHOT_API_KEY", False
    ),
    "openrouter": ProviderInfo(
        "https://openrouter.ai/api/v1/chat/completions", "OPENROUTER_API_KEY", False
    ),
}


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input_usd_per_million: Decimal
    output_usd_per_million: Decimal


@dataclass(frozen=True)
class ModelSetting:
    provider: str
    model: str
    price: Price | None


_MODEL_VAR: dict[Tier, str] = {"cheap": "AI_CHEAP_MODEL", "strong": "AI_STRONG_MODEL"}
_PRICE_VAR: dict[Tier, str] = {"cheap": "AI_CHEAP_PRICE", "strong": "AI_STRONG_PRICE"}
_MICRO = Decimal("0.000001")


def _parse_price(tier: Tier, raw: str | None) -> Price | None:
    if raw is None or not raw.strip():
        return None
    problem = AiNotConfiguredError(
        f'{_PRICE_VAR[tier]} must look like "inputUsdPerMillion,outputUsdPerMillion".'
    )
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        raise problem
    numbers: list[Decimal] = []
    for part in parts:
        try:
            number = Decimal(part)
        except InvalidOperation:
            raise problem from None
        if not number.is_finite() or number < 0:
            raise problem
        numbers.append(number)
    return Price(numbers[0], numbers[1])


def read_tier(tier: Tier, env: Env | None = None) -> ModelSetting:
    """Read one tier's model setting from the environment, or fail visibly."""
    source = os.environ if env is None else env
    raw = (source.get(_MODEL_VAR[tier]) or "").strip()
    if not raw:
        raise AiNotConfiguredError(
            f"AI is not configured: set {_MODEL_VAR[tier]} "
            '(for example "deepseek/<model-id>").'
        )
    provider, _, model = raw.partition("/")
    if not model or provider not in PROVIDERS:
        raise AiNotConfiguredError(
            f'{_MODEL_VAR[tier]} must look like "provider/model-id" with a '
            f"provider from: {', '.join(PROVIDERS)}."
        )
    return ModelSetting(
        provider, model, _parse_price(tier, source.get(_PRICE_VAR[tier]))
    )


def create_provider(
    setting: ModelSetting,
    env: Env | None = None,
    client: "httpx.AsyncClient | None" = None,
) -> "OpenAiCompatibleProvider":
    """Build the provider adapter for a setting; the key is read at call time."""
    from engine.ai.openai_compatible import OpenAiCompatibleProvider

    source = os.environ if env is None else env
    info = PROVIDERS[setting.provider]
    api_key = (source.get(info.key_env) or "").strip()
    if not api_key:
        raise AiNotConfiguredError(
            f"AI is not configured: set {info.key_env} for the "
            f"{setting.provider} provider."
        )
    return OpenAiCompatibleProvider(
        name=setting.provider,
        url=info.url,
        api_key=api_key,
        json_mode=info.json_mode,
        client=client,
    )


def cost_usd(tokens_in: int, tokens_out: int, price: Price | None) -> Decimal | None:
    """Cost in USD rounded to six decimals, or `None` when no price is configured."""
    if price is None:
        return None
    cost = (
        Decimal(tokens_in) * price.input_usd_per_million
        + Decimal(tokens_out) * price.output_usd_per_million
    ) / Decimal(1_000_000)
    return cost.quantize(_MICRO, rounding=ROUND_HALF_UP)
