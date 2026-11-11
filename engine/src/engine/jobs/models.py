"""A job in and out, and the keys that spot a duplicate. Bodies use camelCase."""

import hashlib
import re
import unicodedata
import uuid
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from engine.cv.parse import _clean, _clean_or_none
from engine.models import Job

MAX_JOBS = 500
MAX_BODY_BYTES = 256 * 1024
MAX_RAW_CHARS = 100_000
MIN_RAW_CHARS = 5
MIN_DESCRIPTION_CHARS = 1
MAX_DESCRIPTION_CHARS = 30_000
MAX_URL_CHARS = 2000

Status = Literal["saved", "dismissed"]
Kind = Literal["job", "gig", "ai_training"]

Company = Annotated[
    str, BeforeValidator(_clean), StringConstraints(min_length=1, max_length=120)
]
Title = Annotated[
    str, BeforeValidator(_clean), StringConstraints(min_length=1, max_length=200)
]
Location = Annotated[
    Annotated[str, StringConstraints(max_length=120)] | None,
    BeforeValidator(_clean_or_none),
]
Url = Annotated[
    Annotated[str, StringConstraints(max_length=MAX_URL_CHARS)] | None,
    BeforeValidator(_clean_or_none),
]


class JobIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: Company
    title: Title
    text: str = Field(min_length=MIN_RAW_CHARS, max_length=MAX_RAW_CHARS)
    location: Location = None
    url: Url = None
    kind: Kind = "job"


class JobPatch(BaseModel):
    """A change to a saved job: its status, its type, or both."""

    model_config = ConfigDict(extra="forbid")

    status: Status | None = None
    kind: Kind | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> "JobPatch":
        if self.status is None and self.kind is None:
            raise ValueError("nothing to change")
        return self


class JobOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: uuid.UUID
    company: str
    title: str
    location: str | None
    source_url: str | None = Field(serialization_alias="sourceUrl")
    status: str
    kind: str
    flag: str
    findings: dict[str, int]
    created_at: datetime = Field(serialization_alias="createdAt")


class JobFull(JobOut):
    description: str


def summary(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        company=job.company,
        title=job.title,
        location=job.location,
        source_url=job.source_url,
        status=job.status,
        kind=job.kind,
        flag=job.flag,
        findings=dict(job.findings),
        created_at=job.created_at,
    )


def full(job: Job) -> JobFull:
    return JobFull(**summary(job).model_dump(), description=job.description)


def _fold(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).casefold().strip()


def dedupe_key(company: str, title: str) -> str:
    """The same company and title, however spelled or cased, give the same key."""
    digest = hashlib.sha256(f"{_fold(company)}\0{_fold(title)}".encode()).hexdigest()
    return digest[:32]


def url_key(url: str | None) -> str | None:
    """The address without what does not change the page, or None when it is not usable.

    Only http and https, no embedded credentials; the scheme and host are lowercased,
    the fragment, `utm_*` parameters and a trailing slash are dropped.
    """
    if url is None:
        return None
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ValueError("bad url") from None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise ValueError("bad url")
    if parts.username or parts.password:
        raise ValueError("bad url")
    host = parts.hostname.lower()
    netloc = host if port is None else f"{host}:{port}"
    query = urlencode(
        [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
        ]
    )
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


class FetchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=MAX_URL_CHARS)


class FetchOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    text: str
    title: str | None
    final_url: str = Field(serialization_alias="finalUrl")
    truncated: bool
