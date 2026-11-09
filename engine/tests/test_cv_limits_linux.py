"""Memory-limit behaviour. `RLIMIT_AS` is not enforced on macOS, so these run on Linux
only; run them once in Docker (the command is in AGENTS.md)."""

import sys
import textwrap

import pytest

from engine.cv.extract import ExtractionError
from engine.cv.limits import MIB
from engine.cv.runner import run_extraction
from tests.cv_fixtures import make_expanding_pdf

pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="RLIMIT_AS is enforced on Linux only"
)


async def test_a_pdf_whose_stream_inflates_to_300_mb_is_refused() -> None:
    bomb = make_expanding_pdf(300 * MIB)
    assert len(bomb) < MIB
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(bomb, "pdf")
    assert caught.value.reason in {"unreadable", "no_text"}


async def test_a_child_that_allocates_past_the_cap_is_killed() -> None:
    script = textwrap.dedent(
        """
        from engine.cv.worker import apply_limits
        apply_limits(256 * 1024 * 1024, 5)
        blob = bytearray(600 * 1024 * 1024)
        print('{"ok": true, "text": "survived"}')
        """
    )
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(b"x", "pdf", command=[sys.executable, "-I", "-c", script])
    assert caught.value.reason == "unreadable"
