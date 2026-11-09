"""The isolated extraction path: results match in-process, and limits hold."""

import os
import sys
import textwrap
import time

import pytest

from engine.cv.extract import ExtractionError, Kind, extract_text
from engine.cv.runner import run_extraction
from tests.cv_fixtures import (
    make_bomb_xml,
    make_docx,
    make_docx_with_hidden_entry,
    make_docx_with_xml,
    make_encrypted_pdf,
    make_pdf,
    make_zip,
)

CASES: list[tuple[str, bytes, Kind]] = [
    ("pdf", make_pdf(["Jane Doe", "Flutter engineer"]), "pdf"),
    ("docx", make_docx(["Jane Doe", "Flutter engineer"]), "docx"),
    ("no text pdf", make_pdf([""]), "pdf"),
    ("encrypted", make_encrypted_pdf(), "pdf"),
    ("not a docx", make_zip({"a.txt": b"x"}), "docx"),
    ("corrupt", b"PK\x03\x04 broken", "docx"),
    ("bomb", make_docx_with_xml(make_bomb_xml(30 * 1024 * 1024)), "docx"),
    ("hidden", make_docx_with_hidden_entry(30 * 1024 * 1024), "docx"),
]


def inline(script: str) -> list[str]:
    """A stand-in worker: `python -I -c <script>`; the kind arrives as argv[1]."""
    return [sys.executable, "-I", "-c", textwrap.dedent(script)]


@pytest.mark.parametrize(("name", "data", "kind"), CASES, ids=[c[0] for c in CASES])
async def test_isolated_result_matches_in_process(
    name: str, data: bytes, kind: Kind
) -> None:
    try:
        expected: str | None = extract_text(data, kind)
        expected_reason = None
    except ExtractionError as error:
        expected, expected_reason = None, error.reason
    if expected is not None:
        assert await run_extraction(data, kind) == expected
    else:
        with pytest.raises(ExtractionError) as caught:
            await run_extraction(data, kind)
        # A crash is always `unreadable`; otherwise the same stable reason.
        assert caught.value.reason in {expected_reason, "unreadable"}


async def test_a_child_that_outlives_the_wall_clock_is_killed() -> None:
    command = inline("import time; time.sleep(60)")
    started = time.monotonic()
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(b"x", "pdf", command=command, wall_seconds=1)
    assert caught.value.reason == "unreadable"
    assert time.monotonic() - started < 3


async def test_a_busy_child_is_stopped_by_the_cpu_limit() -> None:
    command = inline(
        """
        from engine.cv.worker import apply_limits
        apply_limits(1 << 30, 1)
        while True:
            pass
        """
    )
    started = time.monotonic()
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(b"x", "pdf", command=command, wall_seconds=10)
    assert caught.value.reason == "unreadable"
    assert time.monotonic() - started < 5


async def test_output_over_the_cap_is_stopped() -> None:
    command = inline("import sys; sys.stdout.write('a' * 5_000_000)")
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(b"x", "pdf", command=command, max_output_bytes=100_000)
    assert caught.value.reason == "unreadable"


async def test_the_child_sees_none_of_the_engine_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENGINE_TOKEN", "t" * 40)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@h/db")
    command = inline(
        """
        import json, os
        print(json.dumps({"ok": True, "text": repr(sorted(os.environ))}))
        """
    )
    text = await run_extraction(b"x", "pdf", command=command)
    assert "TOKEN" not in text
    assert "DATABASE" not in text


@pytest.mark.parametrize(
    "script",
    [
        "print('not json')",
        "print('[1]')",
        'print(\'{"ok": true, "text": 5}\')',
        'print(\'{"ok": false, "reason": "weird"}\')',
        "import sys; sys.exit(3)",
        "import os, signal; os.kill(os.getpid(), signal.SIGKILL)",
    ],
)
async def test_bad_child_results_are_unreadable(script: str) -> None:
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(b"x", "pdf", command=inline(script))
    assert caught.value.reason == "unreadable"


async def test_a_reason_the_child_reports_is_passed_on() -> None:
    command = inline('print(\'{"ok": false, "reason": "no_text"}\')')
    with pytest.raises(ExtractionError) as caught:
        await run_extraction(b"x", "pdf", command=command)
    assert caught.value.reason == "no_text"


async def test_at_most_two_children_run_at_once() -> None:
    import asyncio

    command = inline(
        """
        import time, json
        time.sleep(0.6)
        print(json.dumps({"ok": True, "text": "x"}))
        """
    )
    started = time.monotonic()
    await asyncio.gather(
        *(run_extraction(b"x", "pdf", command=command) for _ in range(4))
    )
    assert time.monotonic() - started >= 1.1


def test_an_already_reaped_child_is_not_signalled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from engine.cv import runner

    sent: list[int] = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: sent.append(pid))
    runner._kill(SimpleNamespace(pid=4242, returncode=0))  # type: ignore[arg-type]
    assert sent == []
    runner._kill(SimpleNamespace(pid=4242, returncode=None))  # type: ignore[arg-type]
    assert sent == [4242]
