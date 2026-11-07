"""Request id middleware and the last-resort handler for unexpected errors."""

import logging
import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from engine.errors import internal_error_response
from engine.jsonlog import accept_request_id, request_id

log = logging.getLogger("engine")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Set the request id, echo it, and turn unexpected errors into a stable 500."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = accept_request_id(request.headers.get("x-request-id"))
        token = request_id.set(rid)
        started = time.monotonic()
        try:
            try:
                response = await call_next(request)
            except Exception as error:  # last-resort handler
                # Log only the error type: messages can carry request data.
                log.error("unhandled error", extra={"error": type(error).__name__})
                response = internal_error_response()
            response.headers["x-request-id"] = rid
            log.info(
                "request",
                extra={
                    "method": request.method,
                    "status": response.status_code,
                    "durationMs": round((time.monotonic() - started) * 1000),
                },
            )
            return response
        finally:
            request_id.reset(token)
