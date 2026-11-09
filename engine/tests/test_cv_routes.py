"""The internal CV routes against a real database and the in-memory store."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from engine.config import Settings
from engine.cv import service
from engine.cv.extract import Kind, extract_text
from engine.cv.limits import MAX_CV_BYTES
from engine.main import create_app
from engine.storage import (
    MemoryStore,
    S3Store,
    StorageUnavailableError,
    load_storage_config,
)
from tests.conftest import TOKEN
from tests.cv_fixtures import make_docx, make_pdf
from tests.db import fetch, upgrade

USER_A = uuid.UUID("3f2b8c1e-7d4a-4c19-9a55-0b6f1d2e3a44")
USER_B = uuid.UUID("9a1c2d3e-4b5f-4a6b-8c7d-0e1f2a3b4c5d")
SECRET_NAME = "Jane-Secret-Name.pdf"
SECRET_TEXT = "Jane-Secret-Text"
FIELDS = {"id", "filename", "mime", "sizeBytes", "parseStatus", "createdAt"}
Stack = tuple[FastAPI, MemoryStore]


async def in_process(data: bytes, kind: Kind) -> str:
    return extract_text(data, kind)


def auth(user: uuid.UUID = USER_A) -> dict[str, str]:
    return {"authorization": f"Bearer {TOKEN}", "x-user-id": str(user)}


def named(user: uuid.UUID = USER_A, name: str = "cv.pdf") -> dict[str, str]:
    return auth(user) | {"x-filename": name}


@pytest.fixture
async def stack(db_url: str) -> AsyncIterator[Stack]:
    await upgrade(db_url)
    app = create_app(Settings(engine_token=TOKEN, database_url=db_url))
    store = MemoryStore()
    app.state.object_store = store
    app.state.extractor = in_process
    yield app, store
    await app.state.database.dispose()


def http(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://engine.test",
    )


async def rows(db_url: str) -> list[dict[str, object]]:
    return await fetch(db_url, "select * from engine.cv_file order by created_at")


async def test_a_pdf_upload_creates_one_object_and_one_row(
    stack: Stack, db_url: str
) -> None:
    app, store = stack
    data = make_pdf(["Jane Doe", "Flutter engineer"])
    async with http(app) as client:
        response = await client.post("/internal/cv", content=data, headers=named())
    assert response.status_code == 201
    body = response.json()
    assert set(body) == FIELDS
    assert body["filename"] == "cv.pdf"
    assert body["mime"] == "pdf"
    assert body["sizeBytes"] == len(data)
    assert body["parseStatus"] == "extracted"
    assert "Jane" not in response.text
    [row] = await rows(db_url)
    assert str(row["id"]) == body["id"]
    assert row["user_id"] == USER_A
    assert "Jane Doe" in str(row["extracted_text"])
    assert str(row["storage_key"]).startswith(f"cv/{USER_A}/")
    assert "cv.pdf" not in str(row["storage_key"])
    assert list(store.objects) == [row["storage_key"]]
    assert store.objects[str(row["storage_key"])][0] == data


async def test_a_docx_upload_with_the_real_isolated_extractor(
    stack: Stack, db_url: str
) -> None:
    app, _ = stack
    app.state.extractor = None  # the real child process
    async with http(app) as client:
        response = await client.post(
            "/internal/cv",
            content=make_docx(["Jane Doe"]),
            headers=named(name="a.docx"),
        )
    assert response.status_code == 201
    assert response.json()["mime"] == "docx"
    [row] = await rows(db_url)
    assert row["extracted_text"] == "Jane Doe"


async def test_the_filename_is_decoded_and_made_display_safe(stack: Stack) -> None:
    app, _ = stack
    data = make_pdf(["x"])
    async with http(app) as client:
        first = await client.post(
            "/internal/cv",
            content=data,
            headers=named(name="Zo%C3%AB%2F..%5Cmy%0ACV.pdf"),
        )
        second = await client.post("/internal/cv", content=data, headers=auth())
    assert first.json()["filename"] == "Zoë..myCV.pdf"
    assert second.json()["filename"] == "cv"


async def test_an_oversized_upload_is_refused_by_header_and_by_stream(
    stack: Stack, db_url: str
) -> None:
    app, store = stack
    big = b"%PDF-" + b"0" * (MAX_CV_BYTES + 1)

    async def chunks() -> AsyncIterator[bytes]:
        for start in range(0, len(big), 65536):
            yield big[start : start + 65536]

    async with http(app) as client:
        by_header = await client.post("/internal/cv", content=big, headers=named())
        by_stream = await client.post("/internal/cv", content=chunks(), headers=named())
    for response in (by_header, by_stream):
        assert response.status_code == 413
        assert response.json()["code"] == "cv_too_large"
    assert store.objects == {}
    assert await rows(db_url) == []


async def test_unsupported_and_unreadable_files_store_nothing(
    stack: Stack, db_url: str
) -> None:
    app, store = stack
    async with http(app) as client:

        async def upload(data: bytes) -> tuple[int, str]:
            response = await client.post("/internal/cv", content=data, headers=named())
            return response.status_code, response.json()["code"]

        assert await upload(b"hello") == (415, "cv_unsupported_type")
        assert await upload(b"") == (415, "cv_unsupported_type")
        assert await upload(b"%PDF-1.4 broken") == (422, "cv_unreadable")
        assert await upload(make_pdf([""])) == (422, "cv_unreadable")
        assert await upload(b"PK\x03\x04 broken") == (422, "cv_unreadable")
    assert store.objects == {}
    assert await rows(db_url) == []


async def test_other_users_and_bad_ids_are_not_found_with_one_body(
    stack: Stack, db_url: str
) -> None:
    app, store = stack
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=named()
        )
        created = response.json()["id"]
        bodies = []
        for method, path in (
            ("GET", f"/internal/cv/{created}/download"),
            ("DELETE", f"/internal/cv/{created}"),
        ):
            variants = (
                path,
                path.replace(created, str(uuid.uuid4())),
                path.replace(created, "not-a-uuid"),
            )
            for variant in variants:
                response = await client.request(method, variant, headers=auth(USER_B))
                assert response.status_code == 404
                bodies.append(response.text)
        own_missing = await client.delete(
            f"/internal/cv/{uuid.uuid4()}", headers=auth(USER_A)
        )
    assert len(set(bodies)) == 1
    assert own_missing.text == bodies[0]
    assert len(await rows(db_url)) == 1
    assert len(store.objects) == 1


async def test_list_is_scoped_newest_first_and_has_no_text(stack: Stack) -> None:
    app, _ = stack
    async with http(app) as client:
        one, two, other = make_pdf(["one"]), make_pdf(["two"]), make_pdf(["b"])
        a1 = await client.post("/internal/cv", content=one, headers=named(name="1.pdf"))
        a2 = await client.post("/internal/cv", content=two, headers=named(name="2.pdf"))
        await client.post("/internal/cv", content=other, headers=named(USER_B))
        mine = await client.get("/internal/cv", headers=auth())
        nobody = await client.get("/internal/cv", headers=auth(uuid.uuid4()))
    ids = [item["id"] for item in mine.json()["items"]]
    assert ids == [a2.json()["id"], a1.json()["id"]]
    assert all(set(item) == FIELDS for item in mine.json()["items"])
    assert "one" not in mine.text
    assert nobody.json() == {"items": []}


async def test_download_returns_a_signed_link_and_delete_removes_both(
    stack: Stack, db_url: str
) -> None:
    app, store = stack
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=named(name="My CV.pdf")
        )
        created = response.json()["id"]
        link = await client.get(f"/internal/cv/{created}/download", headers=auth())
        gone = await client.delete(f"/internal/cv/{created}", headers=auth())
    assert link.status_code == 200
    assert link.json()["expiresInSeconds"] == 300
    assert link.json()["url"].startswith("memory://cv/")
    assert gone.status_code == 204
    assert store.objects == {}
    assert await rows(db_url) == []


class FlakyStore(MemoryStore):
    def __init__(self, *, fail_put: bool = False, fail_delete: bool = False) -> None:
        super().__init__()
        self.fail_put, self.fail_delete = fail_put, fail_delete

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_put:
            raise StorageUnavailableError
        await super().put(key, data, content_type)

    async def delete(self, key: str) -> None:
        if self.fail_delete:
            raise StorageUnavailableError
        await super().delete(key)


async def test_a_storage_failure_on_upload_stores_no_row(
    stack: Stack, db_url: str
) -> None:
    app, _ = stack
    app.state.object_store = FlakyStore(fail_put=True)
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=named()
        )
    assert response.status_code == 502
    assert response.json()["code"] == "storage_unavailable"
    assert await rows(db_url) == []


async def test_a_failed_insert_removes_the_stored_object(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, store = stack

    async def boom(self: object) -> None:
        raise RuntimeError("insert failed")

    monkeypatch.setattr(AsyncSession, "commit", boom)
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=named()
        )
    assert response.status_code == 500
    assert store.objects == {}


async def test_a_storage_failure_on_delete_keeps_the_row(
    stack: Stack, db_url: str
) -> None:
    app, store = stack
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=named()
        )
        created = response.json()["id"]
        flaky = FlakyStore(fail_delete=True)
        flaky.objects = dict(store.objects)
        app.state.object_store = flaky
        failed = await client.delete(f"/internal/cv/{created}", headers=auth())
        assert len(await rows(db_url)) == 1
        flaky.fail_delete = False
        retried = await client.delete(f"/internal/cv/{created}", headers=auth())
    assert failed.status_code == 502
    assert failed.json()["code"] == "storage_unavailable"
    assert retried.status_code == 204
    assert await rows(db_url) == []


async def test_every_cv_route_requires_the_token(stack: Stack) -> None:
    app, store = stack
    some = uuid.uuid4()
    async with http(app) as client:
        for method, path in (
            ("POST", "/internal/cv"),
            ("GET", "/internal/cv"),
            ("GET", f"/internal/cv/{some}/download"),
            ("DELETE", f"/internal/cv/{some}"),
        ):
            for headers in ({}, {"authorization": "Bearer wrong" + "x" * 30}):
                response = await client.request(
                    method, path, headers=headers, content=make_pdf(["x"])
                )
                assert response.status_code == 401
    assert store.objects == {}


async def test_missing_storage_configuration_is_a_stable_503(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = stack
    app.state.object_store = None
    for name in ("STORAGE_ENDPOINT", "STORAGE_BUCKET", "STORAGE_KEY", "STORAGE_SECRET"):
        monkeypatch.delenv(name, raising=False)
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=named()
        )
    assert response.status_code == 503
    assert response.json()["code"] == "storage_not_configured"


_BASE = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message"}


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        extras = {k: v for k, v in record.__dict__.items() if k not in _BASE}
        self.lines.append(f"{record.getMessage()} {extras}")


class Boom:
    """A boto3 stand-in whose errors mention the key, the way real ones can."""

    def __getattr__(self, name: str) -> object:
        def call(*args: object, **kwargs: object) -> object:
            error = {"Error": {"Code": "InternalError", "Message": f"{kwargs}"}}
            raise ClientError(error, name)

        return call


async def test_nothing_sensitive_is_logged_on_any_path(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = stack
    capture = Capture()
    logger = logging.getLogger("engine")
    logger.addHandler(capture)
    logger.setLevel(logging.DEBUG)
    data = make_pdf([SECRET_TEXT])
    headers = named(name=SECRET_NAME)
    try:
        async with http(app) as client:
            response = await client.post("/internal/cv", content=data, headers=headers)
            created = response.json()["id"]
            await client.get("/internal/cv", headers=auth())
            await client.get(f"/internal/cv/{created}/download", headers=auth())
            broken = b"%PDF-1.4 " + SECRET_TEXT.encode()
            await client.post("/internal/cv", content=broken, headers=headers)
            await client.delete(f"/internal/cv/{created}", headers=auth())

            # failure paths: storage down, then a failed insert whose cleanup fails
            app.state.object_store = FlakyStore(fail_put=True)
            await client.post("/internal/cv", content=data, headers=headers)
            app.state.object_store = FlakyStore(fail_delete=True)

            async def boom(self: object) -> None:
                raise RuntimeError(SECRET_NAME)

            with monkeypatch.context() as patch:
                patch.setattr(AsyncSession, "commit", boom)
                await client.post("/internal/cv", content=data, headers=headers)

        # the real S3 adapter failing on every call
        config = load_storage_config(
            {
                "STORAGE_ENDPOINT": "http://s3.test",
                "STORAGE_BUCKET": "b",
                "STORAGE_KEY": "k",
                "STORAGE_SECRET": "s",
            }
        )
        s3 = S3Store(config, client=Boom(), signer=Boom())
        key = f"cv/{USER_A}/secret-key"
        for call in (
            s3.put(key, data, "application/pdf"),
            s3.get(key),
            s3.delete(key),
        ):
            with pytest.raises(StorageUnavailableError):
                await call
        with pytest.raises(StorageUnavailableError):
            s3.signed_url(key, expires_seconds=1, download_name="n")
    finally:
        logger.removeHandler(capture)

    joined = "\n".join(capture.lines)
    assert capture.lines, "expected some log output"
    secrets = (SECRET_NAME, "Secret-Name", SECRET_TEXT, "memory://", "secret-key")
    for secret in (*secrets, str(USER_A)):
        assert secret not in joined
    assert "storage call failed" in joined
    assert "cv cleanup failed after a failed insert" in joined


async def test_a_non_ascii_content_length_is_ignored_not_a_500(stack: Stack) -> None:
    app, _ = stack
    headers = {k.encode(): v.encode() for k, v in named().items()}
    headers[b"content-length"] = b"\xb2"
    async with http(app) as client:
        response = await client.post(
            "/internal/cv", content=make_pdf(["x"]), headers=headers
        )
    assert response.status_code != 500


async def test_a_cancelled_upload_leaves_no_stored_object(
    stack: Stack, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, store = stack
    started = asyncio.Event()

    async def hang(self: object) -> None:
        started.set()
        await asyncio.sleep(60)

    monkeypatch.setattr(AsyncSession, "commit", hang)
    task = asyncio.create_task(
        service.upload_cv(
            user_id=USER_A,
            data=make_pdf(["x"]),
            filename="cv.pdf",
            database=app.state.database,
            store=store,
            extract=in_process,
        )
    )
    await started.wait()
    assert len(store.objects) == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.objects == {}
