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

PARSE_MAX_CHARS = 60_000
"""The most extracted text sent to the model; longer text fails, it is never cut."""

MAX_HEADLINE_CHARS = 200
MAX_SUMMARY_CHARS = 2_000
MAX_EXPERIENCES = 30
MAX_NAME_CHARS = 200
MAX_BULLETS = 20
MAX_BULLET_CHARS = 500
MAX_SKILLS = 100
MAX_SKILL_CHARS = 80
MAX_ACHIEVEMENTS = 100
MAX_ACHIEVEMENT_CHARS = 500
MAX_PROJECTS = 20
MAX_PROJECT_NAME_CHARS = 120
MAX_PROJECT_DESCRIPTION_CHARS = 1_000
MAX_EDUCATION = 10
