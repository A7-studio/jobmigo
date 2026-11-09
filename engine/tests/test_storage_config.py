import pytest

from engine.storage import (
    MemoryStore,
    StorageNotConfiguredError,
    clean_filename,
    content_disposition,
    load_storage_config,
)

FULL = {
    "STORAGE_ENDPOINT": "http://localhost:9100/",
    "STORAGE_BUCKET": "b",
    "STORAGE_KEY": "k",
    "STORAGE_SECRET": "s",
}


def test_loads_values_and_defaults() -> None:
    config = load_storage_config(FULL)
    assert config.endpoint == "http://localhost:9100"
    assert config.public_endpoint == "http://localhost:9100"
    assert config.region == "us-east-1"
    assert config.create_bucket is False


def test_public_endpoint_region_and_local_bucket_creation() -> None:
    config = load_storage_config(
        FULL
        | {
            "STORAGE_PUBLIC_ENDPOINT": "https://files.example.com/",
            "STORAGE_REGION": "auto",
            "ENVIRONMENT": "LOCAL",
        }
    )
    assert config.public_endpoint == "https://files.example.com"
    assert config.region == "auto"
    assert config.create_bucket is True


def test_missing_settings_are_named_without_values() -> None:
    with pytest.raises(StorageNotConfiguredError) as caught:
        load_storage_config(
            {"STORAGE_ENDPOINT": "http://x", "STORAGE_SECRET": "s3cr3t"}
        )
    assert caught.value.status == 503
    assert caught.value.code == "storage_not_configured"
    assert "STORAGE_BUCKET" in caught.value.message
    assert "STORAGE_KEY" in caught.value.message
    assert "s3cr3t" not in caught.value.message


@pytest.mark.parametrize("name", ["STORAGE_ENDPOINT", "STORAGE_PUBLIC_ENDPOINT"])
def test_endpoints_must_be_http_urls(name: str) -> None:
    with pytest.raises(StorageNotConfiguredError) as caught:
        load_storage_config(FULL | {name: "ftp://nope"})
    assert "nope" not in caught.value.message


async def test_memory_store_round_trip() -> None:
    store = MemoryStore()
    assert await store.get("a") is None
    await store.put("a", b"one", "application/pdf")
    await store.put("a", b"two", "application/pdf")
    assert await store.get("a") == b"two"
    await store.delete("a")
    await store.delete("a")
    assert await store.get("a") is None


def test_clean_filename_drops_control_characters_and_separators() -> None:
    assert clean_filename("a/b\\c\x00\n.pdf") == "abc.pdf"
    assert clean_filename("x" * 300) == "x" * 200
    assert clean_filename("  ../etc  ") == "..etc"


def test_content_disposition_has_ascii_fallback_and_utf8_name() -> None:
    value = content_disposition('Zoë "CV"; 100%.pdf')
    assert value.startswith('attachment; filename="Zo_ _CV__ 100_.pdf"')
    assert "filename*=UTF-8''Zo%C3%AB%20%22CV%22%3B%20100%25.pdf" in value
    assert content_disposition("\x00") == (
        "attachment; filename=\"cv\"; filename*=UTF-8''cv"
    )
