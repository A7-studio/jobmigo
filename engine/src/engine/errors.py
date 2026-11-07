"""The stable error shape: every failure is `{ "code": ..., "message": ... }`."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("engine")


class ApiError(Exception):
    """A failure with a status, a stable code and a safe message."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"code": code, "message": message}, status_code=status)


def internal_error_response() -> JSONResponse:
    return error_response(500, "internal_error", "Something went wrong.")


_HTTP_CODES = {404: "not_found", 405: "method_not_allowed"}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError) -> JSONResponse:
        return error_response(error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, __: RequestValidationError) -> JSONResponse:
        # The details can echo request data, so none of it is returned or logged.
        return error_response(422, "invalid_request", "The request is not valid.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, error: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(error.status_code, "http_error")
        response = error_response(error.status_code, code, "Request failed.")
        # Keep headers the framework set, such as Allow on a 405.
        response.headers.update(error.headers or {})
        return response
