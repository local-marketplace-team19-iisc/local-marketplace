"""Terminal CLI for manual smoke-testing the I/O modality decoders.

Usage:
    python -m agent.io.cli transcribe path/to/clip.wav
    python -m agent.io.cli ocr        path/to/photo.jpg

Output: a single JSON object on stdout, e.g.:

    {
      "source": "voice",
      "path": "tests/fixtures/sample_voice.wav",
      "text": "Add 10 kg Sona Masuri rice ...",
      "confidence": 0.91,
      "language": "en",
      "elapsed_ms": 1834
    }

Exit codes:
    0  success
    1  usage / file-not-found
    2  payload too large
    3  low-confidence transcript (voice only) — text was returned, but the
       orchestrator would treat it as a "please retry" turn
    4  too-few characters (OCR only)
    5  missing dependency (faster-whisper / Pillow / tesseract binary)
    6  other runtime error

This file is intentionally tiny: argparse + dispatch + JSON pretty-print.
All real work is in `agent/io/asr.py` and `agent/io/ocr.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from backend.agent.io.asr import (
    ASRDependencyError,
    ASRPayloadTooLargeError,
    transcribe_voice,
)
from backend.agent.io.asr import _asr_cfg as _asr_cfg  # for the threshold knob
from backend.agent.io.ocr import (
    OCRDependencyError,
    OCRImageDecodeError,
    OCRPayloadTooLargeError,
    OCRTooFewCharactersError,
    extract_text_from_image,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _emit(payload: dict[str, Any]) -> None:
    """Print one JSON object on stdout. Stable key order for diffing."""
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _read_bytes_or_exit(path_str: str) -> bytes:
    p = Path(path_str)
    if not p.exists():
        print(f"error: file not found: {p}", file=sys.stderr)
        sys.exit(1)
    if not p.is_file():
        print(f"error: not a regular file: {p}", file=sys.stderr)
        sys.exit(1)
    return p.read_bytes()


# --------------------------------------------------------------------------- #
# Subcommand: transcribe
# --------------------------------------------------------------------------- #


def _cmd_transcribe(args: argparse.Namespace) -> int:
    audio = _read_bytes_or_exit(args.path)

    t0 = time.perf_counter()
    try:
        result = transcribe_voice(audio, language_hint=args.language)
    except ASRPayloadTooLargeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ASRDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(f"error: ASR failed: {exc}", file=sys.stderr)
        return 6
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    threshold = float(getattr(_asr_cfg(), "low_confidence_threshold", 0.6))
    low_conf = result.confidence < threshold

    _emit(
        {
            "source": "voice",
            "path": str(Path(args.path).resolve()),
            "text": result.text,
            "confidence": round(result.confidence, 4),
            "language": result.language,
            "low_confidence": low_conf,
            "threshold": threshold,
            "elapsed_ms": elapsed_ms,
        }
    )
    return 3 if low_conf else 0


# --------------------------------------------------------------------------- #
# Subcommand: ocr
# --------------------------------------------------------------------------- #


def _cmd_ocr(args: argparse.Namespace) -> int:
    image = _read_bytes_or_exit(args.path)

    t0 = time.perf_counter()
    try:
        result = extract_text_from_image(image)
    except OCRTooFewCharactersError as exc:
        print(f"warn: {exc}", file=sys.stderr)
        _emit(
            {
                "source": "image",
                "path": str(Path(args.path).resolve()),
                "text": "",
                "char_count": 0,
                "too_few_chars": True,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            }
        )
        return 4
    except OCRPayloadTooLargeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OCRImageDecodeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 6
    except OCRDependencyError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 5
    except Exception as exc:
        print(f"error: OCR failed: {exc}", file=sys.stderr)
        return 6
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    _emit(
        {
            "source": "image",
            "path": str(Path(args.path).resolve()),
            "text": result.text,
            "char_count": result.char_count,
            "too_few_chars": False,
            "elapsed_ms": elapsed_ms,
        }
    )
    return 0


# --------------------------------------------------------------------------- #
# argparse wiring
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent.io.cli",
        description="Smoke-test the I/O modality decoders (ASR / OCR).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tx = sub.add_parser(
        "transcribe", help="Voice file (.wav/.m4a/.mp3) -> text via Whisper."
    )
    p_tx.add_argument("path", help="Path to the audio file.")
    p_tx.add_argument(
        "--language",
        default=None,
        help="ISO-639-1 hint (e.g. 'en'). Default: read from config/agent.yaml.",
    )
    p_tx.set_defaults(func=_cmd_transcribe)

    p_ocr = sub.add_parser(
        "ocr", help="Image file (.jpg/.png) -> text via Tesseract."
    )
    p_ocr.add_argument("path", help="Path to the image file.")
    p_ocr.set_defaults(func=_cmd_ocr)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
