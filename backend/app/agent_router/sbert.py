"""SBERT model loader (singleton, offline-first).

The model is loaded **once per process**:
  1. If `settings.MODELS_DIR` contains a valid `sentence-transformers`
     snapshot (a directory with `config.json`), load offline from there.
  2. Otherwise, if `settings.ALLOW_MODEL_DOWNLOAD` is true, fall back to a
     `SentenceTransformer(settings.SBERT_MODEL_NAME)` call that may hit the
     network.
  3. Otherwise, raise `SBertModelMissingError` immediately. This is the
     **default** path for CI / corporate-firewall hosts — it surfaces a clear
     "set MODELS_DIR or ALLOW_MODEL_DOWNLOAD=1" message *at app startup*
     rather than hanging on the first request.

The `lru_cache(1)` decorator gives us process-wide singleton behaviour
without a global mutable variable. Tests clear it via `reset_sbert_cache()`.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from backend.app.core.config import settings

if TYPE_CHECKING:  # avoid the ~5 s sentence-transformers import for tests
    from sentence_transformers import SentenceTransformer  # noqa: F401

logger = logging.getLogger(__name__)


class SBertModelMissingError(RuntimeError):
    """Raised at startup when no SBERT snapshot is available and downloads
    are disabled. The message tells the operator exactly which knob to flip.
    """


def _has_snapshot(path: Path) -> bool:
    """Return True iff `path` looks like a sentence-transformers snapshot."""
    if not path.exists() or not path.is_dir():
        return False
    return (path / "config.json").exists() or (path / "config_sentence_transformers.json").exists()


@lru_cache(maxsize=1)
def get_sbert_model() -> "SentenceTransformer":  # type: ignore[name-defined]
    """Return the singleton `SentenceTransformer` model."""
    from sentence_transformers import SentenceTransformer

    snap_dir = Path(settings.MODELS_DIR).expanduser().resolve()
    if _has_snapshot(snap_dir):
        logger.info("sbert: loading from local snapshot %s", snap_dir)
        return SentenceTransformer(str(snap_dir))

    if settings.ALLOW_MODEL_DOWNLOAD or os.getenv("ALLOW_MODEL_DOWNLOAD") == "1":
        logger.warning(
            "sbert: snapshot not found at %s; falling back to network download (%s).",
            snap_dir,
            settings.SBERT_MODEL_NAME,
        )
        return SentenceTransformer(settings.SBERT_MODEL_NAME)

    raise SBertModelMissingError(
        "SBERT model snapshot not found at "
        f"{snap_dir!s} and ALLOW_MODEL_DOWNLOAD is false. "
        "Either run `make sbert-download` to pre-fetch the model into MODELS_DIR, "
        "or set ALLOW_MODEL_DOWNLOAD=1 to allow a one-time download. "
        f"(Configured model: {settings.SBERT_MODEL_NAME!r})"
    )


def reset_sbert_cache() -> None:
    """Drop the cached model. Test-only hook."""
    get_sbert_model.cache_clear()
