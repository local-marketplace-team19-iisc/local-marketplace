"""Tests for `agent/io/ocr.py`.

Two tiers:
- Fast (always run): empty / oversize payload + mocked-tesseract contract.
- Slow (opt-in via `pytest -m slow`): real tesseract on
  `tests/fixtures/sample_image.jpg`. Requires `brew install tesseract`.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.agent.io import ocr as ocr_mod
from backend.agent.io.ocr import (
    MIN_OCR_CHARS,
    OCRImageDecodeError,
    OCRPayloadTooLargeError,
    OCRResult,
    OCRTooFewCharactersError,
    extract_text_from_image,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_IMAGE = FIXTURE_DIR / "sample_image.jpg"


# --------------------------------------------------------------------------- #
# Fast tier
# --------------------------------------------------------------------------- #


def test_extract_empty_payload_raises() -> None:
    with pytest.raises(OCRTooFewCharactersError):
        extract_text_from_image(b"")


def test_extract_rejects_oversize_payload() -> None:
    cfg = ocr_mod._ocr_cfg()
    too_big = b"\xff" * (int(cfg.max_image_bytes) + 1)
    with pytest.raises(OCRPayloadTooLargeError):
        extract_text_from_image(too_big)


def test_extract_rejects_garbage_bytes_as_decode_error() -> None:
    """Non-image bytes within size cap raise OCRImageDecodeError, not crash."""
    garbage = b"not an image at all" * 10
    with pytest.raises(OCRImageDecodeError):
        extract_text_from_image(garbage)


def _make_minimal_png_bytes() -> bytes:
    """A 1x1 white PNG so Pillow.open succeeds inside the mocked test."""
    from io import BytesIO

    from PIL import Image  # type: ignore

    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_extract_with_mocked_tesseract_returns_text() -> None:
    """End-to-end happy path with tesseract patched. Verifies adapter glue."""
    ocr_mod._reset_config_cache_for_tests()

    fake = type("T", (), {"image_to_string": staticmethod(
        lambda img, lang, config: "Sona Masuri Rice 10 kg\n"
    )})()

    with patch.object(ocr_mod, "_tesseract", return_value=fake):
        result = extract_text_from_image(_make_minimal_png_bytes())

    assert isinstance(result, OCRResult)
    assert "Sona Masuri" in result.text
    assert result.char_count == len(result.text)


def test_extract_below_min_chars_raises() -> None:
    """Mocked tesseract returns only whitespace -> too-few-chars error."""
    fake = type("T", (), {"image_to_string": staticmethod(
        lambda img, lang, config: "  \n  \n"
    )})()

    with patch.object(ocr_mod, "_tesseract", return_value=fake):
        with pytest.raises(OCRTooFewCharactersError):
            extract_text_from_image(_make_minimal_png_bytes())


def test_min_chars_threshold_is_loaded_from_config() -> None:
    """Sanity check that the threshold constant matches the config knob."""
    cfg = ocr_mod._ocr_cfg()
    assert int(cfg.min_chars) >= 1
    # The module-level constant stays as the documented default.
    assert MIN_OCR_CHARS == 3


# --------------------------------------------------------------------------- #
# Slow tier — real tesseract, real file
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_extract_real_sample_image() -> None:
    """Run tesseract on `tests/fixtures/sample_image.jpg`.

    Skips automatically if the fixture is missing.
    """
    if not SAMPLE_IMAGE.exists():
        pytest.skip(f"fixture missing: {SAMPLE_IMAGE}")

    ocr_mod._reset_config_cache_for_tests()
    image = SAMPLE_IMAGE.read_bytes()
    result = extract_text_from_image(image)

    assert isinstance(result, OCRResult)
    assert result.char_count >= MIN_OCR_CHARS, (
        f"OCR returned too few chars: {result.text!r}"
    )
