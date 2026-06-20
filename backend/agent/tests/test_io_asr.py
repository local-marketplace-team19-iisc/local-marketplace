"""Tests for `agent/io/asr.py`.

Two tiers:
- Fast (always run): empty payload + mocked-model contract checks. No model
  download, no ffmpeg invocation.
- Slow (opt-in via `pytest -m slow`): load real faster-whisper model and
  transcribe `tests/fixtures/sample_voice.wav`. Requires `brew install ffmpeg`
  and the first run will download the model (~140 MB for base.en).
"""
from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.agent.io import asr as asr_mod
from backend.agent.io.asr import (
    ASRPayloadTooLargeError,
    ASRResult,
    LOW_CONFIDENCE_THRESHOLD,
    transcribe_voice,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE_VOICE = FIXTURE_DIR / "sample_voice.wav"


# --------------------------------------------------------------------------- #
# Fast tier
# --------------------------------------------------------------------------- #


def test_transcribe_empty_payload_is_low_confidence() -> None:
    """Empty bytes must return an empty, low-confidence ASRResult."""
    result = transcribe_voice(b"")
    assert isinstance(result, ASRResult)
    assert result.text == ""
    assert result.confidence == 0.0
    assert result.confidence < LOW_CONFIDENCE_THRESHOLD


def test_transcribe_rejects_oversize_payload() -> None:
    """Bytes above `llm.asr.max_audio_bytes` raise before any model runs."""
    cfg = asr_mod._asr_cfg()
    too_big = b"\x00" * (int(cfg.max_audio_bytes) + 1)
    with pytest.raises(ASRPayloadTooLargeError):
        transcribe_voice(too_big)


def test_confidence_proxy_handles_segments() -> None:
    """The avg_logprob -> exp(mean(...)) proxy gives a [0, 1] number."""
    segs = [
        SimpleNamespace(text="hello", avg_logprob=-0.1),
        SimpleNamespace(text="world", avg_logprob=-0.2),
    ]
    conf = asr_mod._confidence_from_segments(segs)
    expected = (math.exp(-0.1) + math.exp(-0.2)) / 2
    assert conf == pytest.approx(expected, rel=1e-6)
    assert 0.0 <= conf <= 1.0


def test_confidence_proxy_skips_nan_and_missing() -> None:
    segs = [
        SimpleNamespace(text="a", avg_logprob=float("nan")),
        SimpleNamespace(text="b"),  # no avg_logprob attribute -> skipped
        SimpleNamespace(text="c", avg_logprob=-0.5),
    ]
    conf = asr_mod._confidence_from_segments(segs)
    assert conf == pytest.approx(math.exp(-0.5), rel=1e-6)


def test_confidence_proxy_empty_returns_zero() -> None:
    assert asr_mod._confidence_from_segments([]) == 0.0


def test_transcribe_with_mocked_whisper_returns_joined_text() -> None:
    """End-to-end with the Whisper call mocked. Verifies our adapter glue."""
    # Reset caches so our patched _load_model is the one that's used.
    asr_mod._reset_model_cache_for_tests()

    fake_segments = [
        SimpleNamespace(text="Add 10 kg ", avg_logprob=-0.15),
        SimpleNamespace(text="Sona Masuri rice", avg_logprob=-0.12),
    ]
    fake_info = SimpleNamespace(language="en")

    class _FakeModel:
        def transcribe(self, path, **kwargs):  # noqa: ARG002
            return iter(fake_segments), fake_info

    with patch.object(asr_mod, "_load_model", return_value=_FakeModel()):
        result = transcribe_voice(b"\x52\x49\x46\x46fake-wav-bytes")

    # The adapter does ` " ".join(seg.text.strip() ...) ` so per-segment
    # trailing spaces are collapsed into a single inter-segment space.
    assert result.text == "Add 10 kg Sona Masuri rice"
    assert result.language == "en"
    assert 0.0 < result.confidence <= 1.0
    assert result.confidence > LOW_CONFIDENCE_THRESHOLD


# --------------------------------------------------------------------------- #
# Slow tier — real model, real file
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_transcribe_real_sample_voice() -> None:
    """Run faster-whisper on `tests/fixtures/sample_voice.wav`.

    Skips automatically if the fixture isn't present (see
    `tests/fixtures/README.md` for how to record it).
    """
    if not SAMPLE_VOICE.exists():
        pytest.skip(f"fixture missing: {SAMPLE_VOICE}")

    asr_mod._reset_model_cache_for_tests()
    audio = SAMPLE_VOICE.read_bytes()
    result = transcribe_voice(audio)

    assert isinstance(result, ASRResult)
    assert len(result.text) >= 3, f"transcription too short: {result.text!r}"
    assert result.confidence >= LOW_CONFIDENCE_THRESHOLD, (
        f"low confidence on fixture: {result.confidence:.3f}"
    )
