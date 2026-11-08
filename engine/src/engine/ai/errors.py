"""Stable AI errors, in the engine's `{code, message}` shape.

Messages never hold a configuration value, a model reply or a key.
"""

from engine.errors import ApiError


class AiNotConfiguredError(ApiError):
    def __init__(self, message: str) -> None:
        super().__init__(503, "ai_not_configured", message)


class AiUnavailableError(ApiError):
    def __init__(
        self, message: str = "The AI service is unavailable. Try again shortly."
    ) -> None:
        super().__init__(502, "ai_unavailable", message)


class AiOutputInvalidError(ApiError):
    def __init__(
        self, message: str = "The AI returned an answer we could not use."
    ) -> None:
        super().__init__(502, "ai_output_invalid", message)


class AiInputInvalidError(ApiError):
    def __init__(
        self, message: str = "The input for this AI task is not valid."
    ) -> None:
        super().__init__(400, "ai_input_invalid", message)
