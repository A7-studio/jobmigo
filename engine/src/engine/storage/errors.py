"""Stable storage errors, in the engine's `{code, message}` shape.

Messages never hold a key, a signed URL, a configuration value or a response body.
"""

from engine.errors import ApiError


class StorageNotConfiguredError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(503, "storage_not_configured", message)


class StorageUnavailableError(ApiError):
    def __init__(
        self, message: str = "File storage is unavailable. Try again shortly."
    ) -> None:
        super().__init__(502, "storage_unavailable", message)
