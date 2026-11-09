"""Storage settings, read from the environment at call time.

A missing setting fails the call with a message naming the variable, so the engine
still starts without storage and nothing is guessed.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from engine.storage.errors import StorageNotConfiguredError

Env = Mapping[str, str | None]
DEFAULT_REGION = "us-east-1"


@dataclass(frozen=True)
class StorageConfig:
    endpoint: str
    bucket: str
    access_key: str
    secret_key: str
    region: str
    # The address signed download links are built for (see `STORAGE_PUBLIC_ENDPOINT`).
    public_endpoint: str
    # Only local development may create a missing bucket.
    create_bucket: bool


def _value(env: Env, name: str) -> str:
    return (env.get(name) or "").strip()


def load_storage_config(env: Env | None = None) -> StorageConfig:
    source: Env = os.environ if env is None else env
    names = ("STORAGE_ENDPOINT", "STORAGE_BUCKET", "STORAGE_KEY", "STORAGE_SECRET")
    missing = [name for name in names if not _value(source, name)]
    if missing:
        raise StorageNotConfiguredError(
            f"File storage is not configured: set {', '.join(missing)}."
        )
    endpoint = _value(source, "STORAGE_ENDPOINT").rstrip("/")
    if not endpoint.startswith(("http://", "https://")):
        raise StorageNotConfiguredError(
            "File storage is not configured: STORAGE_ENDPOINT must be an http(s) URL."
        )
    public = _value(source, "STORAGE_PUBLIC_ENDPOINT").rstrip("/") or endpoint
    if not public.startswith(("http://", "https://")):
        raise StorageNotConfiguredError(
            "File storage is not configured: "
            "STORAGE_PUBLIC_ENDPOINT must be an http(s) URL."
        )
    return StorageConfig(
        endpoint=endpoint,
        bucket=_value(source, "STORAGE_BUCKET"),
        access_key=_value(source, "STORAGE_KEY"),
        secret_key=_value(source, "STORAGE_SECRET"),
        region=_value(source, "STORAGE_REGION") or DEFAULT_REGION,
        public_endpoint=public,
        create_bucket=_value(source, "ENVIRONMENT").lower() == "local",
    )
