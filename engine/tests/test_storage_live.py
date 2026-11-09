"""Adapter tests against the local RustFS store. Run with STORAGE_LIVE_TEST=1."""

import asyncio
import dataclasses
import os
import uuid
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
import pytest

from engine.storage import (
    S3Store,
    StorageConfig,
    StorageUnavailableError,
    load_storage_config,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("STORAGE_LIVE_TEST") != "1",
    reason="set STORAGE_LIVE_TEST=1 (and start `docker compose up -d storage`)",
)


def _config() -> StorageConfig:
    config = load_storage_config(os.environ | {"ENVIRONMENT": "local"})
    return dataclasses.replace(config, bucket="jobmigo-test")


@pytest.fixture
async def store() -> AsyncIterator[S3Store]:
    yield S3Store(_config())


def _key() -> str:
    return f"cv/test/{uuid.uuid4()}"


async def test_put_get_overwrite_delete_and_missing(store: S3Store) -> None:
    key = _key()
    assert await store.get(key) is None
    await store.put(key, b"one", "application/pdf")
    assert await store.get(key) == b"one"
    await store.put(key, b"two", "application/pdf")
    assert await store.get(key) == b"two"
    await store.delete(key)
    assert await store.get(key) is None
    await store.delete(key)  # a missing object is success


def _get(url: str) -> httpx.Response:
    return httpx.get(url, timeout=10)


async def test_signed_url_downloads_without_credentials(store: S3Store) -> None:
    key = _key()
    await store.put(key, b"hello", "application/pdf")
    url = store.signed_url(key, expires_seconds=60, download_name="My CV.pdf")
    response = _get(url)
    assert response.status_code == 200
    assert response.content == b"hello"
    assert "My CV.pdf" in response.headers["content-disposition"]
    await store.delete(key)


def _edit(url: str, **changes: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query.update(changes)
    return urlunsplit(parts._replace(query=urlencode(query)))


async def test_edited_signed_urls_are_refused(store: S3Store) -> None:
    key, other = _key(), _key()
    await store.put(key, b"mine", "application/pdf")
    # The other object exists, so a missing signature check would return 200.
    await store.put(other, b"theirs", "application/pdf")
    url = store.signed_url(key, expires_seconds=60, download_name="a.pdf")
    assert _get(url).status_code == 200

    other_path = urlsplit(url)._replace(path=urlsplit(url).path.replace(key, other))
    assert _get(urlunsplit(other_path)).status_code == 403

    signature = dict(parse_qsl(urlsplit(url).query))["X-Amz-Signature"]
    flipped = ("0" if signature[0] != "0" else "1") + signature[1:]
    assert _get(_edit(url, **{"X-Amz-Signature": flipped})).status_code == 403
    assert _get(_edit(url, **{"X-Amz-Expires": "604800"})).status_code == 403
    assert (
        _get(_edit(url, **{"response-content-disposition": "inline"})).status_code
        == 403
    )
    await store.delete(key)
    await store.delete(other)


async def test_expired_signed_url_is_refused(store: S3Store) -> None:
    key = _key()
    await store.put(key, b"x", "application/pdf")
    url = store.signed_url(key, expires_seconds=1, download_name="a.pdf")
    await asyncio.sleep(2.5)
    assert _get(url).status_code == 403
    await store.delete(key)


async def test_wrong_secret_is_refused() -> None:
    wrong = dataclasses.replace(_config(), secret_key="not-the-secret")
    with pytest.raises(StorageUnavailableError):
        await S3Store(wrong).put(_key(), b"x", "application/pdf")
