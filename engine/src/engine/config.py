"""Settings read from the environment.

Pydantic's own validation errors echo the rejected value, which would put the
token in a log. `load_settings` turns them into a message that names only the
variables, never their values.
"""

import os
from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

MIN_TOKEN_LENGTH = 32


class ConfigError(Exception):
    """The engine is not configured correctly. The message holds no secret."""


class Settings(BaseModel):
    """Environment variables the engine understands."""

    model_config = ConfigDict(extra="ignore")

    engine_token: str = Field(min_length=MIN_TOKEN_LENGTH)
    database_url: str = Field(min_length=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build settings from `env` (default: the process environment).

    Raises `ConfigError` naming the variables at fault, never their values.
    """
    source = os.environ if env is None else env
    try:
        return Settings.model_validate({k.lower(): v for k, v in source.items()})
    except ValidationError as error:
        names = sorted(
            {str(item["loc"][0]).upper() for item in error.errors() if item["loc"]}
        )

        def describe(name: str) -> str:
            if name == "ENGINE_TOKEN":
                return f"{name} must be set and at least {MIN_TOKEN_LENGTH} characters"
            if name == "DATABASE_URL":
                return f"{name} must be set"
            return f"{name} is not valid"

        detail = "; ".join(describe(name) for name in names)
        raise ConfigError(f"Engine is not configured: {detail}.") from None
