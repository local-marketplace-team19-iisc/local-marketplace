"""Voice clip -> text via faster-whisper.

Module contract (see `agent/io/input-spec.md` and `spec.md` §2.2):

- Input: bytes of an audio file (.wav / .m4a / .mp3 / .webm), <= 10 MB.
- Output: `ASRResult(text, confidence, language)`.
- `confidence < cfg.llm.asr.low_confidence_threshold` -> caller asks the user
  to retry or type the text. We do NOT raise on low confidence; the
  orchestrator decides what to do.

Architectural rules (`spec.md` §2.5):
- This is the ONLY module that may invoke Whisper.
- No imports from `agent.planner`, `agent.tools`, or DB clients.

Implementation notes:
- Engine: faster-whisper (CTranslate2). ~4x faster than openai-whisper on CPU.
- The Whisper model loads lazily on first call and is cached per-process.
- Bytes -> tempfile -> Whisper. Tempfile is removed in a `finally`.
- Confidence proxy: `exp(mean(segment.avg_logprob))` clipped to [0, 1].
  faster-whisper does not expose a single 0..1 confidence; this is the
  standard proxy used by the community.
- All knobs (model, device, beam_size, language, limits) live in
  `config/agent.yaml` under `llm.asr` and are loaded via `utils.config`.
"""
from __future__ import annotations

import math
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from backend.agent.utils.config import load_config

# --------------------------------------------------------------------------- #
# Public dataclass + sentinel exceptions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ASRResult:
    text: str
    confidence: float
    language: str | None = None


class ASRDependencyError(RuntimeError):
    """Raised when faster-whisper is not installed."""


class ASRPayloadTooLargeError(ValueError):
    """Raised when audio_bytes exceeds the configured cap."""


# --------------------------------------------------------------------------- #
# Backwards-compatible constants (kept so tests that import them still pass).
# Authoritative values live in config/agent.yaml -> llm.asr.
# --------------------------------------------------------------------------- #

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_DURATION_SECONDS = 30
LOW_CONFIDENCE_THRESHOLD = 0.6


# --------------------------------------------------------------------------- #
# Config loading (lazy, cached) — single source of truth
# --------------------------------------------------------------------------- #

_CONFIG_LOCK = threading.Lock()
_CACHED_ASR_CFG: Any | None = None


def _asr_cfg() -> Any:
    """Return the `llm.asr` config namespace, loading once per process.

    Prefers the YAML bundled next to the agent package (works from any CWD);
    falls back to the legacy `config/agent.yaml` relative path so older
    callers still work.
    """
    global _CACHED_ASR_CFG
    if _CACHED_ASR_CFG is not None:
        return _CACHED_ASR_CFG
    with _CONFIG_LOCK:
        if _CACHED_ASR_CFG is None:
            from pathlib import Path
            pkg_cfg = Path(__file__).resolve().parents[1] / "config" / "agent.yaml"
            cfg = load_config(str(pkg_cfg) if pkg_cfg.is_file() else "config/agent.yaml")
            _CACHED_ASR_CFG = cfg.llm.asr
    return _CACHED_ASR_CFG


# --------------------------------------------------------------------------- #
# Model loading (lazy singleton, thread-safe)
# --------------------------------------------------------------------------- #

_MODEL_LOCK = threading.Lock()
_MODEL: Any | None = None
_MODEL_KEY: tuple | None = None


def _load_model() -> Any:
    """Return a cached faster-whisper model. Load on first call.

    If `llm.asr.model_path` is set in config and points to an existing
    directory, load from that local folder (offline mode). Otherwise treat
    `llm.asr.model` as a Hugging Face Hub id and let faster-whisper fetch it.
    """
    global _MODEL, _MODEL_KEY

    cfg = _asr_cfg()
    model_id_or_path = _resolve_model_source(cfg)
    key = (model_id_or_path, cfg.device, cfg.compute_type)

    if _MODEL is not None and _MODEL_KEY == key:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is not None and _MODEL_KEY == key:
            return _MODEL

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise ASRDependencyError(
                "faster-whisper is not installed. "
                "Run: pip install -r requirements.txt"
            ) from exc

        _MODEL = WhisperModel(
            model_id_or_path,
            device=cfg.device,
            compute_type=cfg.compute_type,
        )
        _MODEL_KEY = key
        return _MODEL


def _resolve_model_source(cfg: Any) -> str:
    """Return local model path if configured + present, else the Hub id.

    Lets us run fully offline (no Hugging Face Hub access needed) when an
    operator has pre-downloaded the model files into a local directory.
    """
    local_path = getattr(cfg, "model_path", None)
    if local_path:
        p = Path(str(local_path)).expanduser()
        if p.is_dir():
            return str(p)
    return str(cfg.model)


def _reset_model_cache_for_tests() -> None:
    """Test hook: drop the cached model + config so re-config takes effect."""
    global _MODEL, _MODEL_KEY, _CACHED_ASR_CFG
    with _MODEL_LOCK:
        _MODEL = None
        _MODEL_KEY = None
    with _CONFIG_LOCK:
        _CACHED_ASR_CFG = None


# --------------------------------------------------------------------------- #
# Confidence proxy
# --------------------------------------------------------------------------- #


def _confidence_from_segments(segments: Iterable[Any]) -> float:
    """exp(mean(segment.avg_logprob)) clipped to [0, 1].

    faster-whisper returns `avg_logprob` per segment (a negative float, the
    higher i.e. closer to zero the better). We convert via exp() to get a
    pseudo-probability in (0, 1] and average across all segments.

    Empty input -> 0.0 (treat as "no audio detected").
    """
    probs: list[float] = []
    for seg in segments:
        avg_logprob = getattr(seg, "avg_logprob", None)
        if avg_logprob is None or math.isnan(avg_logprob):
            continue
        probs.append(math.exp(avg_logprob))

    if not probs:
        return 0.0
    mean = sum(probs) / len(probs)
    return max(0.0, min(1.0, mean))


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def transcribe_voice(
    audio_bytes: bytes,
    *,
    language_hint: str | None = None,
) -> ASRResult:
    """Transcribe a short voice clip to text.

    Args:
        audio_bytes: Raw audio file content (.wav / .m4a / .mp3 / .webm).
            faster-whisper delegates to ffmpeg for decoding, so any container
            ffmpeg can read works. Caller (HTTP layer) is the primary gatekeeper
            for size/duration. This function performs a defense-in-depth byte cap.
        language_hint: ISO-639-1 code (e.g., "en"). Defaults to the value in
            `config/agent.yaml` (`llm.asr.language_hint`). Pass explicitly to
            override.

    Returns:
        ASRResult with the transcribed text, a confidence score in [0, 1],
        and the detected/hint language.

    Raises:
        ASRPayloadTooLargeError: if len(audio_bytes) > configured cap.
        ASRDependencyError: if faster-whisper is not installed.
    """
    if not audio_bytes:
        # Empty payload -> no audio. Return low-confidence empty result so
        # the orchestrator surfaces a polite "I couldn't hear that" message.
        return ASRResult(text="", confidence=0.0, language=language_hint)

    cfg = _asr_cfg()

    max_bytes = int(getattr(cfg, "max_audio_bytes", MAX_AUDIO_BYTES))
    if len(audio_bytes) > max_bytes:
        raise ASRPayloadTooLargeError(
            f"audio payload {len(audio_bytes)} bytes exceeds cap {max_bytes}"
        )

    model = _load_model()
    lang = language_hint or getattr(cfg, "language_hint", None)
    beam = int(getattr(cfg, "beam_size", 1))

    tmp_path: str | None = None
    try:
        # faster-whisper accepts a file path; bytes path keeps our public
        # contract clean. NamedTemporaryFile with delete=False so we can close
        # then read on Windows-friendly semantics.
        with tempfile.NamedTemporaryFile(
            prefix="asr-", suffix=".audio", delete=False
        ) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments_iter, info = model.transcribe(
            tmp_path,
            language=lang,
            beam_size=beam,
            vad_filter=False,
        )

        # `segments_iter` is a generator; materialise once.
        segments = list(segments_iter)

        text = " ".join((seg.text or "").strip() for seg in segments).strip()
        confidence = _confidence_from_segments(segments)
        detected_lang = getattr(info, "language", None) or lang

        return ASRResult(
            text=text,
            confidence=confidence,
            language=detected_lang,
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                Path(tmp_path).unlink()
            except OSError:
                pass
