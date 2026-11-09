"""Every CV limit, in one place. All are reversible defaults."""

MIB = 1024 * 1024

MAX_CV_BYTES = 5 * MIB
"""The largest upload accepted."""

MAX_TEXT_CHARS = 200_000
"""The most text a CV may yield once extracted."""

MAX_PDF_PAGES = 50
MAX_DOCX_ENTRIES = 1_000
MAX_DOCX_XML_BYTES = 10 * MIB
"""Inflated bytes of `word/document.xml`, counted as they are produced."""

READ_CHUNK = 64 * 1024

WORKER_MEMORY_BYTES = 512 * MIB
"""Address-space cap for the extraction child (`RLIMIT_AS`; Linux only)."""

WORKER_CPU_SECONDS = 10
WORKER_WALL_SECONDS = 15
WORKER_MAX_OUTPUT_BYTES = 4 * MIB
MAX_CONCURRENT_EXTRACTIONS = 2

DOWNLOAD_URL_SECONDS = 300
MAX_LIST_ROWS = 100
MAX_FILENAME_CHARS = 200
