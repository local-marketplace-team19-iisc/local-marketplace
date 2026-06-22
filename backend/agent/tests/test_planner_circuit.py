"""Tests for the CircuitClient (Cisco egai / Azure-OpenAI passthrough).

We stub `httpx.AsyncClient` so the tests run offline. They lock down the
exact wire format we reverse-engineered from the working reference at
`xrSanity2_Project/DDTSMgmt_Backend/llm_description_Genration/
Headline-Desc_CircuitApi.py`:

  * Token POST uses Basic-auth (base64 of client_id:client_secret) and a
    fixed form body `grant_type=client_credentials`. The client_id /
    client_secret never travel in the body.
  * Chat POST goes to
    `<CHAT_URL>/openai/deployments/<model>/chat/completions`.
  * The only auth header on the chat call is `api-key: <token>` — no
    `Authorization: Bearer ...`, no `oauthtoken`.
  * `app-key` is NOT a header; it lives inside `body.user` as a
    JSON-encoded string `{"appkey": "<CIRCUIT_APP_KEY>"}`.
  * `response_format` is NOT sent; the body always includes
    `stop=["<|im_end|>"]`.
"""
from __future__ import annotations

import base64
import json
from typing import Any

import pytest

from backend.agent.planner import CircuitClient


# --------------------------------------------------------------------------- #
# Fake httpx
# --------------------------------------------------------------------------- #


class FakeResponse:
    def __init__(self, status_code: int, payload: Any, *, text: str | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload)

    def json(self) -> Any:
        return self._payload


class FakeAsyncClient:
    """Records calls; returns canned responses queued per URL."""

    def __init__(
        self,
        *,
        token_url: str,
        chat_url_prefix: str,
        token_responses: list[FakeResponse],
        chat_responses: list[FakeResponse],
    ) -> None:
        self._token_url = token_url
        self._chat_url_prefix = chat_url_prefix
        self._token_responses = list(token_responses)
        self._chat_responses = list(chat_responses)
        self.token_calls: list[dict[str, Any]] = []
        self.chat_calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        return None

    async def post(
        self,
        url: str,
        *,
        # Token call uses `content=` (raw bytes/str); chat uses `json=`.
        content: Any = None,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
    ) -> FakeResponse:
        if url == self._token_url:
            self.token_calls.append(
                {"content": content, "data": data, "headers": headers}
            )
            if not self._token_responses:
                raise AssertionError("Unexpected extra token call")
            return self._token_responses.pop(0)
        if url.startswith(self._chat_url_prefix):
            self.chat_calls.append({"json": json, "headers": headers, "url": url})
            if not self._chat_responses:
                raise AssertionError("Unexpected extra chat call")
            return self._chat_responses.pop(0)
        raise AssertionError(f"Unexpected url: {url}")


class FakeTimeout:
    def __init__(self, *_a, **_kw) -> None: ...


class FakeHttpxModule:
    """Drop-in replacement for the `httpx` module the client uses."""

    def __init__(self, fake_client: FakeAsyncClient) -> None:
        self._fake_client = fake_client
        self.Timeout = FakeTimeout

    def AsyncClient(self, *_a, **_kw) -> FakeAsyncClient:
        return self._fake_client


def _build_client(httpx_stub: FakeHttpxModule, **overrides: Any) -> CircuitClient:
    kwargs: dict[str, Any] = dict(
        model="gpt-4o-mini",
        client_id="ID",
        client_secret="SECRET",
        app_key="APP",
        chat_url="https://chat-ai.cisco.com",
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        timeout_s=10,
    )
    kwargs.update(overrides)
    c = CircuitClient(**kwargs)
    c._httpx = httpx_stub  # type: ignore[assignment]
    return c


def _ok_chat_payload(text: str = "{}") -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": text}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _expected_basic(client_id: str = "ID", client_secret: str = "SECRET") -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


# --------------------------------------------------------------------------- #
# 1. Required env vars
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("missing", [
    "client_id", "client_secret", "app_key", "chat_url", "token_url",
])
def test_constructor_rejects_missing_env(missing: str):
    kwargs = dict(
        model="m", client_id="ID", client_secret="SECRET", app_key="APP",
        chat_url="https://chat", token_url="https://token",
    )
    kwargs[missing] = ""
    with pytest.raises(ValueError, match="CIRCUIT_"):
        CircuitClient(**kwargs)


# --------------------------------------------------------------------------- #
# 2 + 5. Happy path: token fetched once, chat wire format is correct
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_complete_fetches_token_then_reuses_it():
    fake = FakeAsyncClient(
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        chat_url_prefix="https://chat-ai.cisco.com/openai/deployments/",
        token_responses=[
            FakeResponse(200, {"access_token": "tok-1", "expires_in": 3600}),
        ],
        chat_responses=[
            FakeResponse(200, _ok_chat_payload('{"ok":true}')),
            FakeResponse(200, _ok_chat_payload('{"ok":true}')),
        ],
    )
    client = _build_client(FakeHttpxModule(fake))

    text1, usage1 = await client.complete(
        system="sys", messages=[{"role": "user", "content": "hi"}],
        temperature=0.0, max_output_tokens=128, response_format_json=True,
    )
    text2, usage2 = await client.complete(
        system="sys", messages=[{"role": "user", "content": "again"}],
        temperature=0.0, max_output_tokens=128, response_format_json=True,
    )

    assert text1 == '{"ok":true}'
    assert text2 == '{"ok":true}'
    assert usage1 == {"prompt_tokens": 10, "completion_tokens": 5}
    assert usage2 == usage1

    # ----- Token call --------------------------------------------------- #
    # ONE token call across two chats (cache reuse).
    assert len(fake.token_calls) == 1
    tcall = fake.token_calls[0]
    assert tcall["content"] == "grant_type=client_credentials"
    # client_id / client_secret must NOT appear in the body.
    assert tcall["data"] is None
    assert tcall["headers"]["Content-Type"] == "application/x-www-form-urlencoded"
    assert tcall["headers"]["Authorization"] == _expected_basic()

    # ----- Chat calls --------------------------------------------------- #
    expected_url = (
        "https://chat-ai.cisco.com/openai/deployments/gpt-4o-mini/chat/completions"
    )
    assert len(fake.chat_calls) == 2
    for call in fake.chat_calls:
        assert call["url"] == expected_url

        h = call["headers"]
        # api-key is the *only* auth header. No Bearer, no oauthtoken.
        assert h["api-key"] == "tok-1"
        assert h["Content-Type"] == "application/json"
        assert "Authorization" not in h
        assert "oauthtoken" not in h
        assert "app-key" not in h  # app-key lives in body.user, not in headers

        body = call["json"]
        # No top-level model on the Azure deployment endpoint.
        assert "model" not in body
        # No response_format — Circuit rejects unknown fields on some routes.
        assert "response_format" not in body
        assert body["messages"][0] == {"role": "system", "content": "sys"}
        assert body["temperature"] == 0.0
        assert body["max_tokens"] == 128
        assert body["stop"] == ["<|im_end|>"]
        # `user` is a JSON-encoded string carrying the app-key.
        assert isinstance(body["user"], str)
        assert json.loads(body["user"]) == {"appkey": "APP"}


# --------------------------------------------------------------------------- #
# 3. Token refresh when within the refresh margin
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_complete_refreshes_token_when_near_expiry():
    fake = FakeAsyncClient(
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        chat_url_prefix="https://chat-ai.cisco.com/openai/deployments/",
        token_responses=[
            # TTL 30s < refresh margin 60s -> next call must refresh.
            FakeResponse(200, {"access_token": "tok-1", "expires_in": 30}),
            FakeResponse(200, {"access_token": "tok-2", "expires_in": 3600}),
        ],
        chat_responses=[
            FakeResponse(200, _ok_chat_payload()),
            FakeResponse(200, _ok_chat_payload()),
        ],
    )
    client = _build_client(FakeHttpxModule(fake))

    await client.complete(
        system="s", messages=[], temperature=0.0,
        max_output_tokens=10, response_format_json=False,
    )
    await client.complete(
        system="s", messages=[], temperature=0.0,
        max_output_tokens=10, response_format_json=False,
    )

    assert len(fake.token_calls) == 2
    assert fake.chat_calls[0]["headers"]["api-key"] == "tok-1"
    assert fake.chat_calls[1]["headers"]["api-key"] == "tok-2"


# --------------------------------------------------------------------------- #
# 4. 401 triggers refresh + one-shot retry
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_complete_retries_once_on_401():
    fake = FakeAsyncClient(
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        chat_url_prefix="https://chat-ai.cisco.com/openai/deployments/",
        token_responses=[
            FakeResponse(200, {"access_token": "tok-1", "expires_in": 3600}),
            FakeResponse(200, {"access_token": "tok-2", "expires_in": 3600}),
        ],
        chat_responses=[
            FakeResponse(401, {}, text="expired"),
            FakeResponse(200, _ok_chat_payload("ok")),
        ],
    )
    client = _build_client(FakeHttpxModule(fake))

    text, _ = await client.complete(
        system="s", messages=[], temperature=0.0,
        max_output_tokens=10, response_format_json=False,
    )
    assert text == "ok"
    assert len(fake.token_calls) == 2
    assert fake.chat_calls[0]["headers"]["api-key"] == "tok-1"
    assert fake.chat_calls[1]["headers"]["api-key"] == "tok-2"


# --------------------------------------------------------------------------- #
# 5. Hard failure path: chat 500 -> RuntimeError
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_complete_raises_on_chat_5xx():
    fake = FakeAsyncClient(
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        chat_url_prefix="https://chat-ai.cisco.com/openai/deployments/",
        token_responses=[FakeResponse(200, {"access_token": "tok", "expires_in": 3600})],
        chat_responses=[FakeResponse(503, {}, text="overloaded")],
    )
    client = _build_client(FakeHttpxModule(fake))
    with pytest.raises(RuntimeError, match="503"):
        await client.complete(
            system="s", messages=[], temperature=0.0,
            max_output_tokens=10, response_format_json=False,
        )


# --------------------------------------------------------------------------- #
# 6. Hard failure path: token endpoint returns non-2xx
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_get_token_raises_on_token_endpoint_failure():
    fake = FakeAsyncClient(
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        chat_url_prefix="https://chat-ai.cisco.com/openai/deployments/",
        token_responses=[FakeResponse(403, {}, text="forbidden")],
        chat_responses=[],
    )
    client = _build_client(FakeHttpxModule(fake))
    with pytest.raises(RuntimeError, match="token request failed"):
        await client.complete(
            system="s", messages=[], temperature=0.0,
            max_output_tokens=10, response_format_json=False,
        )


# --------------------------------------------------------------------------- #
# 7. Chat URL uses the configured model (deployment name)
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_chat_url_uses_configured_model():
    fake = FakeAsyncClient(
        token_url="https://id.cisco.com/oauth2/default/v1/token",
        chat_url_prefix="https://chat-ai.cisco.com/openai/deployments/",
        token_responses=[FakeResponse(200, {"access_token": "tok", "expires_in": 3600})],
        chat_responses=[FakeResponse(200, _ok_chat_payload())],
    )
    client = _build_client(FakeHttpxModule(fake), model="gpt-4o")
    await client.complete(
        system="s", messages=[], temperature=0.0,
        max_output_tokens=10, response_format_json=False,
    )
    assert fake.chat_calls[0]["url"] == (
        "https://chat-ai.cisco.com/openai/deployments/gpt-4o/chat/completions"
    )
