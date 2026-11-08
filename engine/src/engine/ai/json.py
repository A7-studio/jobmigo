"""Pull one JSON value out of a model reply and validate it, without echoing it.

A failure reason holds only field paths and error types, so it is safe to log and
to send back to the model in a retry prompt.
"""

import json
import re
import types
from dataclasses import dataclass
from typing import Annotated, Any, Union, get_args, get_origin

from pydantic import BaseModel, ValidationError

_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_LIST_TYPES = (list, set, frozenset, tuple)


def _reject_constant(_: str) -> object:
    raise ValueError("not JSON")


def _try_parse(text: str) -> tuple[bool, object]:
    try:
        return True, json.loads(text, parse_constant=_reject_constant)
    except ValueError:
        return False, None


def extract_json(text: str) -> tuple[bool, object]:
    """Parse a plain, fenced, or lightly wrapped reply. Returns `(ok, value)`."""
    candidates = [text.strip()]
    fenced = _FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1).strip())
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        if not candidate:
            continue
        ok, value = _try_parse(candidate)
        if ok:
            return True, value
    return False, None


@dataclass(frozen=True)
class Parsed[T: BaseModel]:
    ok: bool
    value: T | None = None
    reason: str = ""


def _strip(annotation: Any) -> Any:
    """Unwrap `Annotated` and optional types down to the type that holds names."""
    while True:
        origin = get_origin(annotation)
        if origin is Annotated:
            annotation = get_args(annotation)[0]
        elif origin in (Union, types.UnionType):
            members = [a for a in get_args(annotation) if a is not type(None)]
            if len(members) != 1:
                return None
            annotation = members[0]
        else:
            return annotation


def _element(annotation: Any) -> Any:
    if get_origin(annotation) in _LIST_TYPES:
        args = get_args(annotation)
        return args[0] if args else None
    return None


def _safe_path(model: type[BaseModel], loc: tuple[int | str, ...]) -> str:
    """Describe an issue location using only names that exist in the schema itself.

    Keys the model chose (a dict key, a union member) are shown as `*`, so the text
    can never carry model-generated content into logs or the retry prompt.
    """
    current: Any = model
    parts: list[str] = []
    for segment in loc:
        current = _strip(current)
        if isinstance(segment, int):
            parts.append(str(segment))
            current = _element(current)
        elif (
            isinstance(segment, str)
            and isinstance(current, type)
            and issubclass(current, BaseModel)
            and segment in current.model_fields
        ):
            parts.append(segment)
            current = current.model_fields[segment].annotation
        else:
            parts.append("*")
            current = None
    return ".".join(parts)


def parse_model_output[T: BaseModel](text: str, model: type[T]) -> Parsed[T]:
    """Parse a model reply against a model. The reason never holds the reply."""
    ok, value = extract_json(text)
    if not ok:
        return Parsed(False, reason="the reply was not valid JSON")
    try:
        return Parsed(True, value=model.model_validate(value))
    except ValidationError as error:
        problems = [
            f"{_safe_path(model, item['loc']) or '(root)'}: {item['type']}"
            for item in error.errors()[:5]
        ]
        return Parsed(
            False, reason=f"the JSON did not match the schema ({'; '.join(problems)})"
        )
