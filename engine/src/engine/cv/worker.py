"""The extraction child: `python -I -m engine.cv.worker <pdf|docx>`.

Reads one file from stdin, prints one JSON line on stdout and exits. It limits its own
memory, CPU, open files and core dumps before it reads anything, so a hostile file can
only hurt this process. The parent adds a wall-clock limit and an output cap.
"""

import json
import resource
import sys

from engine.cv.limits import (
    MAX_CV_BYTES,
    WORKER_CPU_SECONDS,
    WORKER_MEMORY_BYTES,
)


def apply_limits(memory_bytes: int, cpu_seconds: int) -> None:
    """Lower this process's own resource limits. Memory is enforced on Linux only."""
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))


def main(argv: list[str]) -> int:
    kind = argv[1] if len(argv) > 1 else ""
    if kind not in ("pdf", "docx"):
        return 2
    apply_limits(WORKER_MEMORY_BYTES, WORKER_CPU_SECONDS)

    from engine.cv.extract import ExtractionError, extract_text

    data = sys.stdin.buffer.read(MAX_CV_BYTES + 1)
    result: dict[str, object]
    try:
        result = {"ok": True, "text": extract_text(data, kind)}  # type: ignore[arg-type]
    except ExtractionError as error:
        result = {"ok": False, "reason": error.reason}
    sys.stdout.write(json.dumps(result))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
