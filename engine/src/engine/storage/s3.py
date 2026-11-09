"""An S3-compatible adapter (RustFS locally, R2 or B2 in production).

Uses boto3 for Signature V4 and runs its blocking calls in a thread. Errors are mapped
to stable codes and never carry a key, a URL or a response body; the logs hold only the
operation and the error class.
"""

import asyncio
import logging
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from engine.storage.config import StorageConfig
from engine.storage.errors import StorageUnavailableError
from engine.storage.store import content_disposition

log = logging.getLogger("engine")

_MISSING_OBJECT = {"NoSuchKey", "404", "NotFound"}
_MISSING_BUCKET = {"NoSuchBucket"}


def _code(error: ClientError) -> str:
    return str(error.response.get("Error", {}).get("Code", ""))


def _client(config: StorageConfig, endpoint: str) -> Any:
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=config.access_key,
        aws_secret_access_key=config.secret_key,
        region_name=config.region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


class S3Store:
    def __init__(
        self,
        config: StorageConfig,
        *,
        client: Any = None,
        signer: Any = None,
    ) -> None:
        self._config = config
        self._client = client or _client(config, config.endpoint)
        # Presigning is local (no network): it only needs the address to sign for.
        self._signer = signer or (
            self._client
            if config.public_endpoint == config.endpoint
            else _client(config, config.public_endpoint)
        )

    def _fail(self, operation: str, error: Exception) -> StorageUnavailableError:
        log.warning(
            "storage call failed",
            extra={"operation": operation, "error": type(error).__name__},
        )
        return StorageUnavailableError()

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        def run() -> None:
            try:
                self._put(key, data, content_type)
            except (ClientError, BotoCoreError) as error:
                raise self._fail("put", error) from None

        await asyncio.to_thread(run)

    def _put(self, key: str, data: bytes, content_type: str) -> None:
        bucket = self._config.bucket
        try:
            self._client.put_object(
                Bucket=bucket, Key=key, Body=data, ContentType=content_type
            )
        except ClientError as error:
            if not (self._config.create_bucket and _code(error) in _MISSING_BUCKET):
                raise
            self._client.create_bucket(Bucket=bucket)
            self._client.put_object(
                Bucket=bucket, Key=key, Body=data, ContentType=content_type
            )

    async def get(self, key: str) -> bytes | None:
        def run() -> bytes | None:
            try:
                response = self._client.get_object(Bucket=self._config.bucket, Key=key)
                body: bytes = response["Body"].read()
                return body
            except ClientError as error:
                if _code(error) in _MISSING_OBJECT:
                    return None
                raise self._fail("get", error) from None
            except BotoCoreError as error:
                raise self._fail("get", error) from None

        return await asyncio.to_thread(run)

    async def delete(self, key: str) -> None:
        def run() -> None:
            try:
                self._client.delete_object(Bucket=self._config.bucket, Key=key)
            except ClientError as error:
                if _code(error) in _MISSING_OBJECT | _MISSING_BUCKET:
                    return
                raise self._fail("delete", error) from None
            except BotoCoreError as error:
                raise self._fail("delete", error) from None

        await asyncio.to_thread(run)

    def signed_url(self, key: str, *, expires_seconds: int, download_name: str) -> str:
        try:
            url: str = self._signer.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._config.bucket,
                    "Key": key,
                    "ResponseContentDisposition": content_disposition(download_name),
                },
                ExpiresIn=expires_seconds,
            )
        except (ClientError, BotoCoreError) as error:
            raise self._fail("sign", error) from None
        return url
