"""Ports of web/tests/ai-provider.test.ts (each test names its source case)."""

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

import httpx
import pytest

from engine.ai.errors import AiUnavailableError
from engine.ai.openai_compatible import OpenAiCompatibleProvider
from engine.ai.provider import AiRequest, AiResponse

OK = {
    "choices": [{"message": {"content": '{"a":1}'}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 5},
}
REQUEST = AiRequest(model="m1", system="sys", user="hello")
Handler = Callable[[httpx.Request], httpx.Response | Awaitable[httpx.Response]]


class Recorder:
    """Wraps a handler and remembers every request it served."""

    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.requests: list[httpx.Request] = []

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        result = self.handler(request)
        return await result if isinstance(result, Awaitable) else result


def provider(recorder: Recorder, json_mode: bool = True) -> OpenAiCompatibleProvider:
    return OpenAiCompatibleProvider(
        name="test",
        url="https://example.test/chat/completions",
        api_key="secret-key",
        json_mode=json_mode,
        client=httpx.AsyncClient(transport=httpx.MockTransport(recorder)),
        retry_delay_s=0,
    )


def reply(body: object, status: int = 200) -> Handler:
    return lambda _: httpx.Response(status, json=body)


async def test_returns_text_and_token_counts_from_a_good_response() -> None:
    # 'returns text and token counts from a good response'
    recorder = Recorder(reply(OK))
    result = await provider(recorder).complete(REQUEST)
    assert result == AiResponse(text='{"a":1}', tokens_in=12, tokens_out=5)
    request = recorder.requests[0]
    assert str(request.url) == "https://example.test/chat/completions"
    assert request.headers["authorization"] == "Bearer secret-key"
    body = json.loads(request.content)
    assert body["model"] == "m1"
    assert body["response_format"] == {"type": "json_object"}


async def test_omits_response_format_when_the_provider_does_not_document_it() -> None:
    # 'omits response_format when the provider does not document it'
    recorder = Recorder(reply(OK))
    await provider(recorder, json_mode=False).complete(REQUEST)
    assert "response_format" not in json.loads(recorder.requests[0].content)


async def test_treats_missing_usage_as_zero_tokens() -> None:
    # 'treats missing usage as zero tokens'
    recorder = Recorder(reply({"choices": [{"message": {"content": "x"}}]}))
    assert await provider(recorder).complete(REQUEST) == AiResponse("x", 0, 0)


async def test_retries_once_after_a_429_and_then_succeeds() -> None:
    # 'retries once after a 429 and then succeeds'
    answers = iter([httpx.Response(429, json={}), httpx.Response(200, json=OK)])
    recorder = Recorder(lambda _: next(answers))
    result = await provider(recorder).complete(REQUEST)
    assert result.text == '{"a":1}'
    assert len(recorder.requests) == 2


async def test_fails_after_a_persistent_500_with_a_generic_error() -> None:
    # 'fails after a persistent 500 with a generic error'
    recorder = Recorder(reply({"error": "secret provider detail"}, 500))
    with pytest.raises(AiUnavailableError) as caught:
        await provider(recorder).complete(REQUEST)
    assert "secret" not in caught.value.message
    assert caught.value.code == "ai_unavailable"
    assert len(recorder.requests) == 2


async def test_retries_a_network_error_once_then_fails() -> None:
    # 'retries a network error or timeout once, then fails'
    def boom(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    recorder = Recorder(boom)
    with pytest.raises(AiUnavailableError):
        await provider(recorder).complete(REQUEST)
    assert len(recorder.requests) == 2


async def test_does_not_retry_a_401_or_other_client_error() -> None:
    # 'does not retry a 401 or other client error'
    recorder = Recorder(reply({}, 401))
    with pytest.raises(AiUnavailableError):
        await provider(recorder).complete(REQUEST)
    assert len(recorder.requests) == 1


@pytest.mark.parametrize(
    "body",
    [
        {"choices": [], "usage": {"prompt_tokens": 9, "completion_tokens": 3}},
        {
            "choices": [{"message": {"content": None}}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 3},
        },
    ],
)
async def test_returns_empty_text_with_the_tokens_when_the_reply_has_no_content(
    body: object,
) -> None:
    # 'returns empty text with the tokens when the reply has no content'
    recorder = Recorder(reply(body))
    assert await provider(recorder).complete(REQUEST) == AiResponse("", 9, 3)
    assert len(recorder.requests) == 1


async def test_fails_when_the_body_is_not_json_without_retrying() -> None:
    # 'fails when the body is not JSON, without retrying'
    recorder = Recorder(lambda _: httpx.Response(200, text="<html>oops</html>"))
    with pytest.raises(AiUnavailableError):
        await provider(recorder).complete(REQUEST)
    assert len(recorder.requests) == 1


async def test_aborts_a_call_that_outlives_its_time_limit() -> None:
    # 'aborts a call that outlives its time limit'
    async def slow(_: httpx.Request) -> httpx.Response:
        await asyncio.sleep(10)
        return httpx.Response(200, json=OK)

    recorder = Recorder(slow)
    started = time.monotonic()
    with pytest.raises(AiUnavailableError):
        await provider(recorder).complete(
            AiRequest(model="m1", system="sys", user="hello", timeout_s=0.02)
        )
    assert len(recorder.requests) == 2
    assert time.monotonic() - started < 2


async def test_never_logs_the_prompt_the_key_or_the_reply(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # 'never logs the prompt, the key or the reply'
    caplog.set_level(logging.DEBUG, logger="engine")
    recorder = Recorder(reply({"error": "reply-detail"}, 500))
    with pytest.raises(AiUnavailableError):
        await provider(recorder).complete(
            AiRequest(model="m", system="sys-text", user="cv-text")
        )
    logged = "\n".join(
        f"{record.getMessage()} {record.__dict__}" for record in caplog.records
    )
    assert "ai provider call failed" in logged
    for secret in ("cv-text", "sys-text", "secret-key", "reply-detail"):
        assert secret not in logged


async def test_a_200_with_an_error_body_is_unavailable_and_not_retried() -> None:
    # open finding F-48: a gateway can answer 200 with an error object
    recorder = Recorder(reply({"error": {"message": "overloaded"}}))
    with pytest.raises(AiUnavailableError):
        await provider(recorder).complete(REQUEST)
    assert len(recorder.requests) == 1


async def test_joins_the_text_parts_when_content_is_a_list() -> None:
    # open finding F-48: some gateways return content as a list of parts
    body = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": '{"a":'},
                        {"type": "image", "url": "x"},
                        {"type": "text", "text": "1}"},
                    ]
                }
            }
        ],
        "usage": {"prompt_tokens": 4, "completion_tokens": 2},
    }
    result = await provider(Recorder(reply(body))).complete(REQUEST)
    assert result == AiResponse('{"a":1}', 4, 2)
