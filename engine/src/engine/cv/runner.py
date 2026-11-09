"""Run extraction in a child process and turn every outcome into text or a reason.

The child gets an empty environment (no project secrets), no stderr, a wall-clock limit
and a cap on what the parent will read back. Any crash, signal, timeout or malformed
output is `unreadable`; nothing from the file is logged or put in an error.
"""

import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
import weakref
from collections.abc import Sequence

from engine.cv.extract import ExtractionError, Kind, Reason
from engine.cv.limits import (
    MAX_CONCURRENT_EXTRACTIONS,
    MAX_TEXT_CHARS,
    WORKER_MAX_OUTPUT_BYTES,
    WORKER_WALL_SECONDS,
)

log = logging.getLogger("engine")

WORKER_COMMAND = (sys.executable, "-I", "-m", "engine.cv.worker")
_REASONS = {
    "unsupported",
    "unreadable",
    "no_text",
    "too_long",
    "too_many_pages",
    "too_large",
}
_semaphores: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore] = (
    weakref.WeakKeyDictionary()
)


def _semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    found = _semaphores.get(loop)
    if found is None:
        found = _semaphores[loop] = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)
    return found


def _failed(cause: str) -> ExtractionError:
    log.warning("cv extraction failed", extra={"cause": cause})
    return ExtractionError("unreadable")


async def _feed(stdin: asyncio.StreamWriter, data: bytes) -> None:
    try:
        stdin.write(data)
        await stdin.drain()
        stdin.close()
    except (BrokenPipeError, ConnectionResetError):
        pass  # the child already stopped; its exit status says why


async def _collect(stdout: asyncio.StreamReader, cap: int) -> bytes:
    out = bytearray()
    while chunk := await stdout.read(64 * 1024):
        out += chunk
        if len(out) > cap:
            raise _failed("output_too_large")
    return bytes(out)


def _kill(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return  # already reaped: its pid may belong to someone else now
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(process.pid, signal.SIGKILL)


async def run_extraction(
    data: bytes,
    kind: Kind,
    *,
    command: Sequence[str] = WORKER_COMMAND,
    wall_seconds: float = WORKER_WALL_SECONDS,
    max_output_bytes: int = WORKER_MAX_OUTPUT_BYTES,
) -> str:
    """The text of `data`, or `ExtractionError`. `command` and limits are test seams."""
    async with _semaphore():
        process = await asyncio.create_subprocess_exec(
            *command,
            kind,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env={},
            start_new_session=True,
        )
        try:
            if process.stdin is None or process.stdout is None:
                raise _failed("no_pipes")
            async with asyncio.timeout(wall_seconds):
                _, output = await asyncio.gather(
                    _feed(process.stdin, data),
                    _collect(process.stdout, max_output_bytes),
                )
                code = await process.wait()
        except TimeoutError:
            raise _failed("timeout") from None
        finally:
            _kill(process)
            await process.wait()

    if code != 0:
        raise _failed("exit_signal" if code < 0 else "exit_code")
    return _parse(output)


def _parse(output: bytes) -> str:
    try:
        result = json.loads(output)
    except ValueError:
        raise _failed("bad_output") from None
    if not isinstance(result, dict):
        raise _failed("bad_output")
    if result.get("ok") is True:
        text = result.get("text")
        if not isinstance(text, str) or not text.strip():
            raise _failed("bad_output")
        if len(text) > MAX_TEXT_CHARS:
            raise ExtractionError("too_long")
        return text
    reason = result.get("reason")
    if isinstance(reason, str) and reason in _REASONS:
        reasoned: Reason = reason  # type: ignore[assignment]
        raise ExtractionError(reasoned)
    raise _failed("bad_output")
