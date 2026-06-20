"""Image -> text via Tesseract (pytesseract + Pillow).

Module contract (see `agent/io/input-spec.md` and `spec.md` §2.2):

- Input: bytes of an image file (.jpg / .png / .webp / .bmp), <= 5 MB.
- Output: `OCRResult(text, char_count)`.
- If extracted text has < `cfg.llm.ocr.min_chars` printable characters,
  raise `OCRTooFewCharactersError` so the orchestrator surfaces a polite
  "I couldn't read the image" message — never forward empty text to the LLM.

Architectural rules (`spec.md` §2.5):
- This is the ONLY module that may invoke Tesseract / an OCR engine.
- No imports from `agent.planner`, `agent.tools`, or DB clients.

Implementation notes:
- Engine: Tesseract via `pytesseract`. Requires the `tesseract` binary on PATH
  (macOS: `brew install tesseract`).
- Preprocessing (baseline): open via Pillow, EXIF-orient, convert to grayscale.
  Heavier preprocessing (binarization, denoise) is deferred to Phase 2.
- All knobs (lang, psm, oem, limits, min_chars) live in `config/agent.yaml`
  under `llm.ocr` and are loaded via `utils.config`.
"""
from __future__ import annotations

import io
import threading
from dataclasses import dataclass
from typing import Any

from backend.agent.utils.config import load_config

# --------------------------------------------------------------------------- #
# Public dataclass + sentinel exceptions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class OCRResult:
    text: str
    char_count: int


class OCRTooFewCharactersError(ValueError):
    """Raised when OCR yields fewer than `min_chars` printable characters."""


class OCRDependencyError(RuntimeError):
    """Raised when pytesseract / the tesseract binary is not available."""


class OCRPayloadTooLargeError(ValueError):
    """Raised when image_bytes exceeds the configured cap."""


class OCRImageDecodeError(ValueError):
    """Raised when Pillow cannot decode the image bytes."""


# --------------------------------------------------------------------------- #
# Backwards-compatible constants (kept so imports + tests keep working).
# Authoritative values live in config/agent.yaml -> llm.ocr.
# --------------------------------------------------------------------------- #

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MIN_OCR_CHARS = 3


# --------------------------------------------------------------------------- #
# Config loading (lazy, cached)
# --------------------------------------------------------------------------- #

_CONFIG_LOCK = threading.Lock()
_CACHED_OCR_CFG: Any | None = None


def _ocr_cfg() -> Any:
    """Return the `llm.ocr` config namespace, loading once per process.

    Resolves config/agent.yaml relative to the agent package so OCR works
    regardless of CWD.
    """
    global _CACHED_OCR_CFG
    if _CACHED_OCR_CFG is not None:
        return _CACHED_OCR_CFG
    with _CONFIG_LOCK:
        if _CACHED_OCR_CFG is None:
            from pathlib import Path
            pkg_cfg = Path(__file__).resolve().parents[1] / "config" / "agent.yaml"
            cfg = load_config(str(pkg_cfg) if pkg_cfg.is_file() else "config/agent.yaml")
            _CACHED_OCR_CFG = cfg.llm.ocr
    return _CACHED_OCR_CFG


def _reset_config_cache_for_tests() -> None:
    """Test hook: drop the cached config so re-config takes effect."""
    global _CACHED_OCR_CFG
    with _CONFIG_LOCK:
        _CACHED_OCR_CFG = None


# --------------------------------------------------------------------------- #
# Engine accessor (lazy import, raises a friendly error if missing)
# --------------------------------------------------------------------------- #


def _tesseract() -> Any:
    try:
        import pytesseract  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise OCRDependencyError(
            "pytesseract is not installed. "
            "Run: pip install -r requirements.txt"
        ) from exc
    return pytesseract


def _pillow() -> Any:
    try:
        from PIL import Image, ImageOps  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise OCRDependencyError(
            "Pillow is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return Image, ImageOps


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def extract_text_from_image(image_bytes: bytes) -> OCRResult:
    """Extract text from an image.

    Args:
        image_bytes: Raw image file content (.jpg / .png / .webp / .bmp).
            Caller (HTTP layer) is the primary gatekeeper for size; this
            function performs a defense-in-depth byte cap.

    Returns:
        OCRResult with extracted text and printable-character count.

    Raises:
        OCRTooFewCharactersError: if printable-char count < configured min.
        OCRPayloadTooLargeError: if len(image_bytes) > configured cap.
        OCRImageDecodeError: if Pillow cannot decode the bytes.
        OCRDependencyError: if pytesseract / Pillow / tesseract binary missing.
    """
    if not image_bytes:
        raise OCRTooFewCharactersError("empty image payload")

    cfg = _ocr_cfg()

    max_bytes = int(getattr(cfg, "max_image_bytes", MAX_IMAGE_BYTES))
    if len(image_bytes) > max_bytes:
        raise OCRPayloadTooLargeError(
            f"image payload {len(image_bytes)} bytes exceeds cap {max_bytes}"
        )

    min_chars = int(getattr(cfg, "min_chars", MIN_OCR_CHARS))
    lang = str(getattr(cfg, "lang", "eng"))
    psm = int(getattr(cfg, "psm", 6))
    oem = int(getattr(cfg, "oem", 3))

    Image, ImageOps = _pillow()
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Honour EXIF rotation (phone photos are routinely sideways).
        img = ImageOps.exif_transpose(img)
        img = img.convert("L")  # grayscale
    except Exception as exc:
        raise OCRImageDecodeError(f"could not decode image: {exc}") from exc

    tesseract = _tesseract()
    try:
        # `--oem N --psm N` controls engine + page segmentation mode.
        config_str = f"--oem {oem} --psm {psm}"
        raw_text: str = tesseract.image_to_string(img, lang=lang, config=config_str)
    except Exception as exc:  # pragma: no cover
        # pytesseract raises a generic Exception if the tesseract binary is
        # missing or fails. Surface as a dependency error.
        raise OCRDependencyError(
            f"tesseract invocation failed: {exc}. "
            "Is the `tesseract` binary on PATH? (brew install tesseract)"
        ) from exc

    text = (raw_text or "").strip()
    # Count printable, non-whitespace characters for the min-chars check.
    # Newlines/spaces shouldn't count toward "meaningful content".
    printable_chars = sum(1 for c in text if not c.isspace())

    if printable_chars < min_chars:
        raise OCRTooFewCharactersError(
            f"OCR returned {printable_chars} printable characters "
            f"(min {min_chars})"
        )

    return OCRResult(text=text, char_count=len(text))
