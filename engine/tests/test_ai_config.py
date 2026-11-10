"""Ports of web/tests/ai-config.test.ts (each test names its source case)."""

from collections.abc import Callable
from decimal import Decimal

import pytest

from engine.ai.config import ModelSetting, Price, cost_usd, create_provider, read_tier
from engine.ai.errors import AiNotConfiguredError


def config_error(run: Callable[[], object]) -> str:
    with pytest.raises(AiNotConfiguredError) as caught:
        run()
    assert caught.value.code == "ai_not_configured"
    assert caught.value.status == 503
    return caught.value.message


def test_reads_provider_model_and_price() -> None:
    # readTier: 'reads provider, model and price'
    setting = read_tier(
        "cheap", {"AI_CHEAP_MODEL": "deepseek/some-model", "AI_CHEAP_PRICE": "0.3, 1.2"}
    )
    assert setting == ModelSetting(
        "deepseek", "some-model", Price(Decimal("0.3"), Decimal("1.2"))
    )


def test_keeps_slashes_inside_the_model_id() -> None:
    # readTier: 'keeps slashes inside the model id'
    setting = read_tier("strong", {"AI_STRONG_MODEL": "openrouter/vendor/model-x"})
    assert setting.provider == "openrouter"
    assert setting.model == "vendor/model-x"
    assert setting.price is None


def test_names_the_variable_when_the_tier_is_not_set() -> None:
    # readTier: 'names the variable when the tier is not set'
    assert "AI_CHEAP_MODEL" in config_error(lambda: read_tier("cheap", {}))


def test_rejects_malformed_settings_without_echoing_the_value() -> None:
    # readTier: 'rejects malformed settings without echoing the value'
    message = config_error(
        lambda: read_tier("cheap", {"AI_CHEAP_MODEL": "nonsense-value"})
    )
    assert "AI_CHEAP_MODEL" in message
    assert "nonsense-value" not in message
    assert "deepseek" in config_error(
        lambda: read_tier("cheap", {"AI_CHEAP_MODEL": "unknown/m"})
    )
    assert "AI_CHEAP_MODEL" in config_error(
        lambda: read_tier("cheap", {"AI_CHEAP_MODEL": "deepseek/"})
    )


@pytest.mark.parametrize(
    "price", ["1", "a,b", "-1,2", "1,2,3", "5,", ",5", ",", "nan,1"]
)
def test_rejects_a_malformed_price(price: str) -> None:
    # readTier: 'rejects a malformed price'
    message = config_error(
        lambda: read_tier(
            "cheap", {"AI_CHEAP_MODEL": "deepseek/m", "AI_CHEAP_PRICE": price}
        )
    )
    assert "AI_CHEAP_PRICE" in message
    assert price not in message or price in ("1", ",")  # never echo odd values


def test_names_the_missing_key_variable_never_a_value() -> None:
    # createProvider: 'names the missing key variable, never a value'
    message = config_error(
        lambda: create_provider(ModelSetting("moonshot", "m", None), {})
    )
    assert "MOONSHOT_API_KEY" in message


def test_builds_a_provider_when_the_key_is_present() -> None:
    # createProvider: 'builds a provider when the key is present'
    provider = create_provider(
        ModelSetting("deepseek", "m", None), {"DEEPSEEK_API_KEY": "secret-key"}
    )
    assert provider.name == "deepseek"


def test_cost_is_computed_from_tokens_and_rounded_to_six_decimals() -> None:
    # costUsd: 'computes cost from tokens and rounds to six decimals'
    price = Price(Decimal("0.3"), Decimal("1.2"))
    assert cost_usd(1_000_000, 500_000, price) == Decimal("0.9")
    assert cost_usd(1000, 1000, price) == Decimal("0.0015")
    assert cost_usd(1, 0, price) == Decimal("0")
    assert cost_usd(0, 0, price) == Decimal("0")
    assert cost_usd(1, 1, Price(Decimal("0.5"), Decimal("0"))) == Decimal("0.000001")


def test_cost_is_none_without_a_price() -> None:
    # costUsd: 'is null without a price'
    assert cost_usd(100, 100, None) is None


def test_knows_the_free_tier_providers() -> None:
    for name in ("gemini", "groq", "cloudflare"):
        assert read_tier("cheap", {"AI_CHEAP_MODEL": f"{name}/m"}).provider == name


def test_cloudflare_needs_an_account_id_that_goes_into_the_url() -> None:
    setting = read_tier("cheap", {"AI_CHEAP_MODEL": "cloudflare/@cf/vendor/m"})
    assert setting.model == "@cf/vendor/m"
    base = {"CLOUDFLARE_API_TOKEN": "t"}
    assert "CLOUDFLARE_ACCOUNT_ID" in config_error(
        lambda: create_provider(setting, base)
    )
    bad = base | {"CLOUDFLARE_ACCOUNT_ID": "../x"}
    assert "CLOUDFLARE_ACCOUNT_ID" in config_error(
        lambda: create_provider(setting, bad)
    )
    good = base | {"CLOUDFLARE_ACCOUNT_ID": "abc123"}
    provider = create_provider(setting, good)
    assert provider._url == (
        "https://api.cloudflare.com/client/v4/accounts/abc123/ai/v1/chat/completions"
    )
