"""Planner: builds the prompt, calls the LLM, parses structured JSON.

The planner is provider-agnostic. The `LLMClient.complete()` method
returns a JSON string; the parser validates it against `PlannerOutput`
and retries once on parse failure with a "fix your JSON" nudge.
"""
from __future__ import annotations

import json
import os
from typing import Any, Protocol

from pydantic import ValidationError

from backend.agent import prompts
from backend.agent.schemas import PlannerOutput, Session, ToolResult
from backend.agent.tools.base import tool_schemas_for_prompt


def _load_dotenv_once() -> None:
    """Load `.env` at import time so OPENAI_API_KEY is visible.

    Best-effort: if `python-dotenv` is not installed, we silently rely on the
    process environment. We never overwrite values already present in env.
    """
    try:
        from dotenv import load_dotenv  # type: ignore
    except ImportError:
        return
    # Walk up from this file to find a .env at the repo root.
    from pathlib import Path

    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        candidate = parent / ".env"
        if candidate.is_file():
            load_dotenv(candidate, override=False)
            return


_load_dotenv_once()


class LLMClient(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_output_tokens: int,
        response_format_json: bool,
    ) -> tuple[str, dict[str, int]]: ...
    # returns (raw_text, {"prompt_tokens": ..., "completion_tokens": ...})


# ---------------------------------------------------------------------------
# Default client implementations
# ---------------------------------------------------------------------------

class StubLLMClient:
    """Deterministic, no-network client for unit tests and local smoke runs.

    The behaviour is intentionally minimal: it produces an empty
    PlannerOutput with a polite fallback message. Replace with
    `OpenAIClient` / `VLLMClient` in production via `build_llm_client(cfg)`.
    """

    async def complete(self, **_kw) -> tuple[str, dict[str, int]]:
        payload = PlannerOutput(
            thought="stub client — no model attached",
            tool_calls=[],
            assistant="(stub) I heard you. Hook up an LLM to get real replies.",
        ).model_dump_json()
        return payload, {"prompt_tokens": 0, "completion_tokens": 0}


class OpenAIClient:
    """Thin wrapper around the OpenAI Chat Completions API."""

    def __init__(self, model: str, timeout_s: int = 20) -> None:
        from openai import AsyncOpenAI  # type: ignore
        self._client = AsyncOpenAI(timeout=timeout_s)
        self._model = model

    async def complete(
        self, *, system: str, messages, temperature, max_output_tokens,
        response_format_json,
    ) -> tuple[str, dict[str, int]]:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            messages=[{"role": "system", "content": system}, *messages],
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await self._client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0,
        }
        return text, usage


class CircuitClient:
    """LLM client for the Cisco Circuit (egai) gateway.

    Wire format mirrors the working reference at
    `xrSanity2_Project/DDTSMgmt_Backend/llm_description_Genration/
    Headline-Desc_CircuitApi.py`. Circuit is a passthrough to Azure OpenAI,
    so we use the Azure conventions:

      Token request:
        POST <token_url>
        Authorization: Basic base64(client_id:client_secret)
        Content-Type: application/x-www-form-urlencoded
        Body: "grant_type=client_credentials"
        -> {access_token, expires_in}

      Chat request:
        POST <chat_url>/openai/deployments/<model>/chat/completions
        api-key: <access_token>          (NO "Bearer " prefix)
        Content-Type: application/json
        Body: {
          "messages":     [...],
          "temperature":  <float>,
          "stop":         ["<|im_end|>"],
          "user":         json.dumps({"appkey": <CIRCUIT_APP_KEY>}),
        }

    Notes:
      - `app-key` does NOT go in a header; it's embedded in `body.user`.
      - We DO NOT send `response_format`: the gateway rejects unknown fields
        on some deployments. JSON shape is enforced by the system prompt
        and our `_safe_parse` tolerates code-fenced JSON.
      - Token TTL is honoured via the cache; refresh fires inside the
        margin (default 60s). One-shot refresh on a 401.
      - Corporate proxies / TLS interception: honours `HTTPS_PROXY` env var
        and disables cert verification when CIRCUIT_VERIFY_SSL=false. The
        DDTSAutomation reference uses verify=False unconditionally; we
        default to verify=True and let ops opt out via env.
    """

    _REFRESH_MARGIN_S = 60  # refresh access_token N seconds before expiry

    def __init__(
        self,
        *,
        model: str,
        client_id: str,
        client_secret: str,
        app_key: str,
        chat_url: str,
        token_url: str,
        timeout_s: int = 90,
        verify_ssl: bool = True,
        proxy: str | None = None,
    ) -> None:
        # Fail fast on missing creds — never silently send empty Bearer.
        for label, value in [
            ("CIRCUIT_CLIENT_ID", client_id),
            ("CIRCUIT_CLIENT_SECRET", client_secret),
            ("CIRCUIT_APP_KEY", app_key),
            ("CIRCUIT_CHAT_URL", chat_url),
            ("CIRCUIT_TOKEN_URL", token_url),
        ]:
            if not value:
                raise ValueError(f"CircuitClient: missing required env var {label}")

        import httpx  # type: ignore  # imported lazily so tests can stub

        self._httpx = httpx
        self._model = model
        self._client_id = client_id
        self._client_secret = client_secret
        self._app_key = app_key
        self._chat_url = chat_url.rstrip("/")
        self._token_url = token_url
        self._timeout = httpx.Timeout(float(timeout_s), connect=10.0)
        self._verify_ssl = verify_ssl
        self._proxy = proxy

        # Token cache
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0  # epoch seconds
        # Serialise token refresh so concurrent turns don't stampede.
        import asyncio
        self._token_lock = asyncio.Lock()

    # ----- internal: build an httpx AsyncClient with proxy + verify ------

    def _new_http(self):
        kwargs: dict[str, Any] = {"timeout": self._timeout, "verify": self._verify_ssl}
        if self._proxy:
            # httpx accepts a single str via `proxy=` from 0.27 onwards;
            # also accepts `proxies=` (dict) for older versions. We use
            # the broadly-compatible `proxies=` form.
            kwargs["proxies"] = {"http://": self._proxy, "https://": self._proxy}
        return self._httpx.AsyncClient(**kwargs)

    # ----- token handling -------------------------------------------------

    async def _get_token(self) -> str:
        import base64
        import time

        # Fast path: cached token still valid.
        now = time.time()
        if self._access_token and now < (self._token_expires_at - self._REFRESH_MARGIN_S):
            return self._access_token

        async with self._token_lock:
            # Re-check inside the lock to avoid duplicate refreshes.
            now = time.time()
            if self._access_token and now < (self._token_expires_at - self._REFRESH_MARGIN_S):
                return self._access_token

            basic = base64.b64encode(
                f"{self._client_id}:{self._client_secret}".encode("utf-8")
            ).decode("utf-8")
            headers = {
                "Accept": "*/*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
            }
            async with self._new_http() as http:
                resp = await http.post(
                    self._token_url,
                    content="grant_type=client_credentials",
                    headers=headers,
                )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"CircuitClient token request failed: "
                    f"{resp.status_code} {resp.text[:200]}"
                )
            payload = resp.json()
            token = payload.get("access_token")
            ttl = int(payload.get("expires_in", 0) or 0)
            if not token:
                raise RuntimeError(
                    f"CircuitClient token response missing access_token: "
                    f"keys={list(payload.keys())}"
                )
            # If the gateway omits expires_in we default to 30 minutes;
            # the reference uses get_fresh_token per-request so this is
            # purely an optimisation.
            if ttl <= 0:
                ttl = 1800
            self._access_token = token
            self._token_expires_at = time.time() + ttl
            return token

    # ----- chat call ------------------------------------------------------

    async def complete(
        self,
        *,
        system: str,
        messages,
        temperature,
        max_output_tokens,
        response_format_json,  # noqa: ARG002 - kept for protocol compatibility
    ) -> tuple[str, dict[str, int]]:
        token = await self._get_token()

        # Circuit / Azure OpenAI deployments accept the standard `messages`
        # array. `response_format` is NOT supported here — we drop it and
        # rely on the system prompt + `_safe_parse` to keep JSON discipline.
        body: dict[str, Any] = {
            "messages": [{"role": "system", "content": system}, *messages],
            "temperature": temperature,
            "max_tokens": max_output_tokens,
            "stop": ["<|im_end|>"],
            # app-key travels INSIDE the body, not as a header.
            "user": json.dumps({"appkey": self._app_key}),
        }
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "api-key": token,
        }
        url = f"{self._chat_url}/openai/deployments/{self._model}/chat/completions"

        async with self._new_http() as http:
            resp = await http.post(url, json=body, headers=headers)

        # One retry on 401 in case the token expired mid-flight. We build a
        # *fresh* headers dict so callers / mocks that captured the first
        # attempt's headers see the original token, not the refreshed one.
        if resp.status_code == 401:
            self._access_token = None  # force refresh
            token = await self._get_token()
            retry_headers = {**headers, "api-key": token}
            async with self._new_http() as http:
                resp = await http.post(url, json=body, headers=retry_headers)

        if resp.status_code >= 400:
            raise RuntimeError(
                f"CircuitClient chat request failed: "
                f"{resp.status_code} {resp.text[:300]}"
            )
        payload = resp.json()
        try:
            text = payload["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"CircuitClient: unexpected chat response shape: {e!r} :: "
                f"{str(payload)[:200]}"
            ) from e
        usage = payload.get("usage") or {}
        return text, {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        }


def build_llm_client(cfg) -> LLMClient:
    """Return the LLM client implied by env + config.

    Selection order (env wins over config; we *always* print which client
    was selected so the user sees it on REPL startup):
      1. CIRCUIT_CLIENT_ID + CIRCUIT_CLIENT_SECRET + CIRCUIT_APP_KEY all set
         -> CircuitClient (Cisco egai gateway).
      2. cfg.llm.planner.provider == "openai" AND OPENAI_API_KEY set
         -> OpenAIClient.
      3. Otherwise -> StubLLMClient.
    """
    import sys

    circuit_id = os.environ.get("CIRCUIT_CLIENT_ID", "").strip()
    circuit_secret = os.environ.get("CIRCUIT_CLIENT_SECRET", "").strip()
    circuit_app = os.environ.get("CIRCUIT_APP_KEY", "").strip()

    if circuit_id and circuit_secret and circuit_app:
        try:
            verify_env = os.environ.get("CIRCUIT_VERIFY_SSL", "").strip().lower()
            verify_ssl = verify_env not in {"0", "false", "no", "off"}
            proxy = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("https_proxy")
                or None
            )
            client = CircuitClient(
                model=os.environ.get("CIRCUIT_MODEL", cfg.llm.planner.model),
                client_id=circuit_id,
                client_secret=circuit_secret,
                app_key=circuit_app,
                chat_url=os.environ.get(
                    "CIRCUIT_CHAT_URL", "https://chat-ai.cisco.com",
                ),
                token_url=os.environ.get(
                    "CIRCUIT_TOKEN_URL",
                    "https://id.cisco.com/oauth2/default/v1/token",
                ),
                timeout_s=int(
                    os.environ.get("CIRCUIT_TIMEOUT", cfg.llm.planner.timeout_s)
                ),
                verify_ssl=verify_ssl,
                proxy=proxy,
            )
            extras = []
            if not verify_ssl:
                extras.append("verify_ssl=false")
            if proxy:
                extras.append(f"proxy={proxy}")
            suffix = (", " + ", ".join(extras)) if extras else ""
            print(
                f"info: planner using CircuitClient (model={client._model}, "
                f"chat_url={client._chat_url}{suffix})",
                file=sys.stderr,
            )
            return client
        except Exception as exc:
            print(f"warn: CircuitClient init failed ({exc}) — trying OpenAI.",
                  file=sys.stderr)

    provider = cfg.llm.planner.provider
    if provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            print(
                "warn: no Circuit creds and OPENAI_API_KEY not set — "
                "falling back to StubLLMClient. Set Circuit env vars in "
                "`.env` to enable real planning.",
                file=sys.stderr,
            )
            return StubLLMClient()
        try:
            client = OpenAIClient(
                cfg.llm.planner.model,
                timeout_s=int(cfg.llm.planner.timeout_s),
            )
            print(
                f"info: planner using OpenAIClient (model={cfg.llm.planner.model})",
                file=sys.stderr,
            )
            return client
        except Exception as exc:
            print(f"warn: OpenAIClient init failed ({exc}) — using StubLLMClient.",
                  file=sys.stderr)
            return StubLLMClient()

    print(f"warn: unknown LLM provider {provider!r} — using StubLLMClient.",
          file=sys.stderr)
    return StubLLMClient()


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

_REPAIR_HINT = (
    "Your previous output was not valid JSON matching the required schema. "
    "Reply again with ONLY a JSON object containing keys "
    "'thought', 'tool_calls', 'assistant'. No prose, no code fences."
)


class Planner:
    def __init__(self, cfg, client: LLMClient) -> None:
        self.cfg = cfg
        self.client = client

    def _system_prompt(self, session: Session) -> str:
        role = session.role
        if role == "vendor":
            tpl = prompts.load("system_vendor.txt")
        elif role == "customer":
            tpl = prompts.load("system_customer.txt")
        else:
            tpl = prompts.load("system_router.txt")

        substitutions = {
            "tool_schemas": json.dumps(
                tool_schemas_for_prompt(role), ensure_ascii=False, indent=2,
            ),
            "lang": session.language,
            "user_id": session.user_id or "anon",
            "location": str(
                session.location.model_dump() if session.location else None
            ),
            "pending_action": str(
                session.pending_action.model_dump()
                if session.pending_action else None
            ),
        }
        # Use a safe placeholder syntax `<<KEY>>` so literal `{...}` JSON
        # examples in the prompt templates don't collide with str.format.
        out = tpl
        for k, v in substitutions.items():
            out = out.replace(f"<<{k}>>", v)
        return out

    def _build_messages(
        self,
        session: Session,
        user_text: str,
        scratchpad: list[ToolResult],
    ) -> list[dict[str, str]]:
        msgs: list[dict[str, str]] = []

        if session.summary:
            msgs.append({"role": "system",
                         "content": f"Conversation summary so far:\n{session.summary}"})

        # Replay the rolling window of past turns. CRITICAL: we replay
        # each prior assistant turn as the JSON envelope the planner is
        # required to emit, NOT the user-facing text. Otherwise the model
        # sees its own past replies as prose and drifts away from the
        # JSON contract within a few turns.
        for turn in session.turns[-self.cfg.session.max_turns_in_context :]:
            msgs.append({"role": "user",
                         "content": _wrap_untrusted(turn.user_msg.text)})
            if turn.assistant_msg and turn.assistant_msg.text:
                envelope = {
                    "thought": "",
                    "tool_calls": [
                        {"name": c.name, "args": c.args} for c in (turn.tool_calls or [])
                    ],
                    "assistant": turn.assistant_msg.text,
                }
                msgs.append({"role": "assistant",
                             "content": json.dumps(envelope, ensure_ascii=False)})

        msgs.append({"role": "user", "content": _wrap_untrusted(user_text)})

        if scratchpad:
            tool_blob = json.dumps(
                [r.model_dump(mode="json") for r in scratchpad],
                ensure_ascii=False,
            )
            msgs.append({"role": "system",
                         "content": f"Tool results so far (trusted):\n{tool_blob}"})
        return msgs

    async def plan(
        self,
        session: Session,
        user_text: str,
        scratchpad: list[ToolResult],
        *,
        for_tool_args: bool,
    ) -> tuple[PlannerOutput, dict[str, int]]:
        system = self._system_prompt(session)
        messages = self._build_messages(session, user_text, scratchpad)
        temperature = (
            self.cfg.llm.planner.temperature_tool if for_tool_args
            else self.cfg.llm.planner.temperature_chat
        )

        raw, usage = await self.client.complete(
            system=system, messages=messages,
            temperature=temperature,
            max_output_tokens=int(self.cfg.llm.planner.max_output_tokens),
            response_format_json=True,
        )
        parsed = _safe_parse(raw)

        if parsed is None:
            # one repair attempt
            messages2 = messages + [
                {"role": "assistant", "content": raw},
                {"role": "system", "content": _REPAIR_HINT},
            ]
            raw2, usage2 = await self.client.complete(
                system=system, messages=messages2,
                temperature=0.0,
                max_output_tokens=int(self.cfg.llm.planner.max_output_tokens),
                response_format_json=True,
            )
            parsed = _safe_parse(raw2) or PlannerOutput(
                thought="parse-failure-fallback",
                tool_calls=[],
                assistant="Sorry, could you rephrase that?",
            )
            usage = {k: usage.get(k, 0) + usage2.get(k, 0) for k in usage | usage2}

        return parsed, usage


def _safe_parse(raw: str) -> PlannerOutput | None:
    """Parse the LLM's reply into a `PlannerOutput`, tolerating common drift.

    Layers of recovery (in order):
      1. Trim whitespace.
      2. Strip ```...``` code fences (optional `json` tag).
      3. If that still doesn't parse, extract the FIRST balanced
         `{ ... }` JSON object from the response (Circuit can't enforce
         response_format=json_object so the LLM occasionally adds a
         "Here's the JSON: ..." prefix).

    Returns `None` only when none of the above yield a `PlannerOutput`.
    """
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()

    # First pass — straight parse.
    candidate = raw
    for attempt in range(2):
        try:
            data = json.loads(candidate)
            return PlannerOutput.model_validate(data)
        except (json.JSONDecodeError, ValidationError):
            if attempt == 1:
                return None
            extracted = _extract_first_json_object(raw)
            if not extracted:
                return None
            candidate = extracted
    return None


def _extract_first_json_object(text: str) -> str | None:
    """Return the first balanced top-level JSON object in `text`.

    Walks the string tracking brace depth, ignoring braces inside string
    literals (with escape handling). Returns None if no balanced `{...}`
    is found. Cheap O(n), no regex backtracking.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _wrap_untrusted(text: str) -> str:
    """Wrap user-provided text so the LLM treats it as data, not instruction."""
    return f"<<<UNTRUSTED>>>\n{text}\n<<<END>>>"
