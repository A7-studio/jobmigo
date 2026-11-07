"""JSON log lines with a request id. Never pass tokens, ids or request data in."""

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", (), None)))


def accept_request_id(candidate: str | None) -> str:
    """Keep a well-formed supplied id, otherwise generate one."""
    if candidate and _SAFE_ID.fullmatch(candidate):
        return candidate
    return str(uuid.uuid4())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "level": record.levelname.lower(),
            "time": datetime.now(UTC).isoformat(),
            "message": record.getMessage(),
            "requestId": request_id.get(),
        }
        line.update({k: v for k, v in record.__dict__.items() if k not in _RESERVED})
        return json.dumps(line, default=str)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("engine")
    logger.setLevel(level.upper())
    logger.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
