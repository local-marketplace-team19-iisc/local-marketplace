"""Interactive REPL for the marketplace agent (baseline).

Usage:
    python -m backend.agent.cli --role vendor
    python -m backend.agent.cli --role customer
    python -m backend.agent.cli --role vendor --override llm.planner.provider=openai

Slash commands inside the REPL:
    /help           Show this help
    /voice <path>   Transcribe an audio file (uses backend/agent/io/asr.py)
    /image <path>   OCR an image file (uses backend/agent/io/ocr.py)
    /catalog        (vendor) Quick local snapshot of the in-memory store
    /reset          Wipe the in-memory store and start a fresh session
    /quit | /exit   Leave the REPL

Anything not starting with `/` is sent verbatim as a user message.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from backend.agent.io.asr import ASRPayloadTooLargeError, transcribe_voice
from backend.agent.io.ocr import (
    OCRImageDecodeError,
    OCRPayloadTooLargeError,
    OCRTooFewCharactersError,
    extract_text_from_image,
)
from backend.agent.orchestrator import Orchestrator
from backend.agent.schemas import Message
from backend.agent.tools import _store
from backend.agent.utils.config import load_config


# Default config path: prefer the YAML bundled next to the agent package so the
# REPL works regardless of the user's CWD. If absent, fall back to the legacy
# repo-root path so existing scripts keep working.
_PACKAGE_CFG = Path(__file__).resolve().parent / "config" / "agent.yaml"
_DEFAULT_CFG = (
    str(_PACKAGE_CFG)
    if _PACKAGE_CFG.is_file()
    else "config/agent.yaml"
)


_HELP_TEXT = """\
commands:
  /help                 show this help
  /voice <path>         transcribe a .wav/.m4a/.mp3 and send as a turn
  /image <path>         OCR a .jpg/.png and send as a turn
  /catalog              snapshot of the in-memory product store
  /reset                wipe the in-memory store + start a fresh session
  /quit | /exit         leave

anything else is sent as a chat message.\
"""


# --------------------------------------------------------------------------- #
# Slash-command helpers
# --------------------------------------------------------------------------- #


def _read_path(path_str: str) -> bytes | None:
    p = Path(path_str.strip().strip("'").strip('"'))
    if not p.is_file():
        print(f"  ! file not found: {p}", file=sys.stderr)
        return None
    return p.read_bytes()


def _decode_voice(path_str: str) -> tuple[str, str] | None:
    """Run ASR. Returns (text, banner) on success, None on hard failure."""
    audio = _read_path(path_str)
    if audio is None:
        return None
    try:
        result = transcribe_voice(audio)
    except ASRPayloadTooLargeError as e:
        print(f"  ! {e}", file=sys.stderr)
        return None
    if not result.text:
        print("  ! voice clip produced no text — try retyping the message.",
              file=sys.stderr)
        return None
    banner = (
        f"  [voice transcribed | confidence={result.confidence:.2f}"
        f"{' (low!)' if result.confidence < 0.6 else ''}]"
    )
    return result.text, banner


def _decode_image(path_str: str) -> tuple[str, str] | None:
    image = _read_path(path_str)
    if image is None:
        return None
    try:
        result = extract_text_from_image(image)
    except OCRTooFewCharactersError as e:
        print(f"  ! OCR couldn't read enough text: {e}", file=sys.stderr)
        return None
    except (OCRPayloadTooLargeError, OCRImageDecodeError) as e:
        print(f"  ! {e}", file=sys.stderr)
        return None
    banner = f"  [image ocr'd | {result.char_count} chars]"
    return result.text, banner


# --------------------------------------------------------------------------- #
# REPL
# --------------------------------------------------------------------------- #


async def repl(cfg, *, role: str | None) -> None:
    _store.reset_store()
    orch = Orchestrator(cfg)
    session_id: str | None = None
    user_id = f"dev_{role or 'guest'}"

    print(f"Marketplace agent — role={role or 'unknown'} — type '/help' for commands.\n")

    while True:
        try:
            raw = input("you> ").rstrip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue

        # --- slash commands ----------------------------------------------
        if raw.startswith("/"):
            cmd, _, arg = raw[1:].partition(" ")
            cmd = cmd.lower()
            if cmd in ("quit", "exit"):
                return
            if cmd == "help":
                print(_HELP_TEXT)
                continue
            if cmd == "reset":
                _store.reset_store()
                session_id = None
                print("  · store cleared; session reset.")
                continue
            if cmd == "catalog":
                snap = _store.snapshot()
                print(f"  · in-memory store: {snap['products']} products, "
                      f"{snap['stores']} stores")
                for p in _store.iter_products():
                    print(f"     - {p.product_id}: {p.name} | {p.quantity} {p.unit} "
                          f"| ₹{p.price} | store={p.store_id}")
                continue
            if cmd in ("voice", "image") and not arg:
                print(f"  ! /{cmd} needs a path argument. Example: /{cmd} tests/fixtures/sample_voice.wav")
                continue
            if cmd == "voice":
                decoded = _decode_voice(arg)
            elif cmd == "image":
                decoded = _decode_image(arg)
            else:
                print(f"  ! unknown command: /{cmd}. Try /help.")
                continue
            if decoded is None:
                continue
            text, banner = decoded
            print(banner)
            print(f"  → sending as user message: {text!r}")
        else:
            text = raw

        # --- normal turn -------------------------------------------------
        resp = await orch.handle_turn(
            session_id=session_id,
            user_id=user_id,
            channel="web",
            user_input=Message(text=text),
        )
        # Stamp the role on the freshly-created session so the planner sees
        # the right system prompt from the very first turn.
        if session_id is None and role:
            session_id = resp.session_id
            sess = await orch.store.get(session_id)
            if sess and sess.role == "unknown":
                sess.role = role  # type: ignore[assignment]
                await orch.store.save(sess)
                # Re-run the same turn now that role is set, so the planner
                # uses the role-specific prompt. This only happens on turn 1.
                resp = await orch.handle_turn(
                    session_id=session_id,
                    user_id=user_id,
                    channel="web",
                    user_input=Message(text=text),
                )
        else:
            session_id = resp.session_id

        print(f"bot> {resp.assistant}")
        if resp.pending_action:
            pa = resp.pending_action
            print(f"     · pending: {pa.tool_name}({pa.args}) — reply 'yes' to confirm or 'no' to cancel.")
        print()


def main() -> None:
    ap = argparse.ArgumentParser(prog="backend.agent.cli")
    ap.add_argument("--config", default=_DEFAULT_CFG)
    ap.add_argument(
        "--override", action="append", default=[],
        help="Dotted override: key.subkey=value",
    )
    ap.add_argument(
        "--role", choices=["vendor", "customer"], default="vendor",
        help="Role for this REPL session (default: vendor).",
    )
    args = ap.parse_args()

    cfg = load_config(args.config, overrides=args.override)
    asyncio.run(repl(cfg, role=args.role))


if __name__ == "__main__":
    main()
