"""Loader contract tests for `backend.app.agent_router.sbert`.

These DO NOT load the real SBERT model — we want a sub-second test that
locks the loader's *decision logic*: snapshot precedence, download
fallback, fail-fast behaviour. The accuracy of the model itself is covered
by `test_intent_classifier.py` (marked `slow`).
"""

from __future__ import annotations

import pytest

from backend.app.agent_router import sbert


@pytest.fixture(autouse=True)
def _reset_cache():
    sbert.reset_sbert_cache()
    yield
    sbert.reset_sbert_cache()


def test_missing_snapshot_and_download_disabled_raises(tmp_path, monkeypatch):
    """No snapshot + ALLOW_MODEL_DOWNLOAD=False → fail fast with a helpful message."""
    monkeypatch.setattr(sbert.settings, "MODELS_DIR", str(tmp_path / "does-not-exist"))
    monkeypatch.setattr(sbert.settings, "ALLOW_MODEL_DOWNLOAD", False)
    monkeypatch.delenv("ALLOW_MODEL_DOWNLOAD", raising=False)

    with pytest.raises(sbert.SBertModelMissingError) as exc:
        sbert.get_sbert_model()

    msg = str(exc.value)
    assert "MODELS_DIR" in msg
    assert "ALLOW_MODEL_DOWNLOAD" in msg


def test_snapshot_path_short_circuits_download(tmp_path, monkeypatch):
    """A directory with `config.json` is treated as a valid snapshot — the
    loader passes the *local path* to SentenceTransformer rather than the
    HF model id."""
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "config.json").write_text("{}")

    monkeypatch.setattr(sbert.settings, "MODELS_DIR", str(snap))
    monkeypatch.setattr(sbert.settings, "ALLOW_MODEL_DOWNLOAD", False)

    captured: dict = {}

    class _Fake:
        def __init__(self, name_or_path):
            captured["name_or_path"] = name_or_path

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", _Fake)

    model = sbert.get_sbert_model()
    assert model is not None
    assert captured["name_or_path"] == str(snap)


def test_download_path_used_when_flag_set(tmp_path, monkeypatch):
    """No snapshot + ALLOW_MODEL_DOWNLOAD=True → loader passes the HF model id."""
    monkeypatch.setattr(sbert.settings, "MODELS_DIR", str(tmp_path / "missing"))
    monkeypatch.setattr(sbert.settings, "ALLOW_MODEL_DOWNLOAD", True)
    monkeypatch.setattr(sbert.settings, "SBERT_MODEL_NAME", "fake/model-id")

    captured: dict = {}

    class _Fake:
        def __init__(self, name_or_path):
            captured["name_or_path"] = name_or_path

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", _Fake)

    sbert.get_sbert_model()
    assert captured["name_or_path"] == "fake/model-id"


def test_cache_returns_same_instance(tmp_path, monkeypatch):
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "config.json").write_text("{}")
    monkeypatch.setattr(sbert.settings, "MODELS_DIR", str(snap))

    calls = {"n": 0}

    class _Fake:
        def __init__(self, name_or_path):
            calls["n"] += 1

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", _Fake)

    a = sbert.get_sbert_model()
    b = sbert.get_sbert_model()
    assert a is b
    assert calls["n"] == 1, "expected the model to be constructed exactly once"


def test_reset_cache_forces_rebuild(tmp_path, monkeypatch):
    snap = tmp_path / "snap"
    snap.mkdir()
    (snap / "config.json").write_text("{}")
    monkeypatch.setattr(sbert.settings, "MODELS_DIR", str(snap))

    calls = {"n": 0}

    class _Fake:
        def __init__(self, name_or_path):
            calls["n"] += 1

    monkeypatch.setattr("sentence_transformers.SentenceTransformer", _Fake)

    sbert.get_sbert_model()
    sbert.reset_sbert_cache()
    sbert.get_sbert_model()
    assert calls["n"] == 2
