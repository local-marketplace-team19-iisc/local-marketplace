"""Intent classifier accuracy suite.

These tests load the **real** SBERT model (~80 MB, ~5-15 s cold on a Mac).
They are marked `slow` so the default `make test` run skips them per the
project's `pyproject.toml [tool.pytest.ini_options] addopts = "-ra -m 'not
slow'"`. To run explicitly:

    pytest backend/tests/test_intent_classifier.py -m slow -v
    # or
    make agent-test

The acceptance bar from spec §3 is **≥ 90% accuracy** across 6 labelled
intents + 5 distractors. We measure with the default
`INTENT_CONFIDENCE_THRESHOLD` (0.45). Failing this test points at one of
three things:
  1. The chosen model changed semantics (rare).
  2. The prototypes in `intents.py` need tuning for your audience.
  3. The threshold needs adjusting — bump `INTENT_CONFIDENCE_THRESHOLD`
     down to catch more low-confidence positives, *but* watch the
     `unknown`-distractor tests below to make sure you don't over-shoot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.agent_router import intents, sbert
from backend.app.core.config import settings


pytestmark = pytest.mark.slow


# --------------------------------------------------------------------------- #
# Fixture: point MODELS_DIR at the developer snapshot if available, else
# permit a one-off download (network required). CI typically pre-downloads.
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True, scope="module")
def _enable_model_load():
    snap = Path(settings.MODELS_DIR).expanduser().resolve()
    if not (snap.exists() and (snap / "config.json").exists()):
        # Allow a one-shot network fetch in dev runs.
        import os

        os.environ.setdefault("ALLOW_MODEL_DOWNLOAD", "1")
    sbert.reset_sbert_cache()
    intents.reset_intent_index_cache()
    yield
    sbert.reset_sbert_cache()
    intents.reset_intent_index_cache()


# --------------------------------------------------------------------------- #
# Labelled utterance suite (5 per intent, 5 distractors → `unknown`).
# Mix of customer and vendor phrasing, written in the spirit of the spec §1
# example queries.
# --------------------------------------------------------------------------- #


CASES: list[tuple[str, str]] = [
    # search_products
    ("Show me iPhone 15 under ₹60,000", "search_products"),
    ("Find second-hand laptops near me", "search_products"),
    ("search for gaming monitors", "search_products"),
    ("I'm looking for cheap rice", "search_products"),
    ("Do you have any bread in stock?", "search_products"),
    # add_product
    ("Add a new Samsung S24 for ₹45,000", "add_product"),
    ("Create a listing for OnePlus 12 priced ₹40000", "add_product"),
    ("I want to list a new product in my store", "add_product"),
    ("register this rice 5kg for ₹500", "add_product"),
    ("put up a new listing for whole wheat bread", "add_product"),
    # update_product
    ("Update the price of my iPhone listing to ₹50,000", "update_product"),
    ("change product 1234 to ₹999", "update_product"),
    ("edit the stock of my Dell laptop", "update_product"),
    ("set a new price for the Samsung phone", "update_product"),
    ("modify my Amul milk listing", "update_product"),
    # delete_product
    ("Delete product ID 12345", "delete_product"),
    ("Remove the milk listing", "delete_product"),
    ("take down my Sona Masuri rice", "delete_product"),
    ("delete this bread from my inventory", "delete_product"),
    ("remove the gaming laptop please", "delete_product"),
    # get_my_listings
    ("Show my listings", "get_my_listings"),
    ("What products do I have?", "get_my_listings"),
    ("list all my products", "get_my_listings"),
    ("what am I currently selling", "get_my_listings"),
    ("show me my own inventory", "get_my_listings"),
    # get_categories
    ("What categories do you have?", "get_categories"),
    ("list the available categories", "get_categories"),
    ("show me product categories", "get_categories"),
    ("what kinds of items do you sell", "get_categories"),
    ("which categories are supported", "get_categories"),
    # unknown / distractors
    ("What's the weather tomorrow?", "unknown"),
    ("how are you today", "unknown"),
    ("play some music", "unknown"),
    ("tell me a joke", "unknown"),
    ("schedule a meeting at 3pm", "unknown"),
]


def test_classifier_accuracy_at_least_90_percent():
    total = len(CASES)
    correct = 0
    misses: list[tuple[str, str, str, float]] = []
    for text, want in CASES:
        got, score = intents.classify(text)
        if got == want:
            correct += 1
        else:
            misses.append((text, want, got, score))
    accuracy = correct / total
    assert accuracy >= 0.9, (
        f"intent classifier accuracy {accuracy:.0%} below 90% bar.\n"
        f"Misses ({len(misses)}/{total}):\n"
        + "\n".join(
            f"  - {t!r} expected={want} got={got} score={score:.3f}"
            for t, want, got, score in misses
        )
    )


def test_unknown_distractors_specifically():
    """Even if the overall accuracy passes, every distractor MUST resolve to
    `unknown` — leaking weather/music chat into one of the six intents would
    silently call a marketplace API on garbage input (spec FR-1)."""
    for text, want in CASES:
        if want != "unknown":
            continue
        got, score = intents.classify(text)
        assert got == "unknown", f"distractor {text!r} leaked into {got!r} (score={score:.3f})"


# --------------------------------------------------------------------------- #
# Regression: terse adds must not be pulled into update/delete by SBERT
# over-fitting to brand-specific prototypes. See Session 6 in
# specs/008-sbert-intent-router/conversation-history.md for the original
# user-reported misclassifications.
# --------------------------------------------------------------------------- #


TERSE_ADD_CASES: list[str] = [
    "add iPhone 50000",                       # was → update_product
    "Add Amul milk for 29",                   # was → delete_product
    "Add Pixel 9 55000",
    "Add a new Samsung S24 for 45000",
    "list Britannia bread for 50",
    "add OnePlus 12 Rs 60000",
    "Add Tata salt 5kg Rs 250",
    "post a new iPhone 15 Pro listing at 89999",
    "i want to sell a new Sony headphone for 8000",
]


@pytest.mark.parametrize("text", TERSE_ADD_CASES)
def test_terse_add_utterances_classify_as_add(text: str):
    """Terse vendor adds (with brand + number, no full sentence) must be
    classified as `add_product`. The verb-prefix tiebreaker is what makes
    this reliable — see `_verb_hint` in `intents.py`."""
    got, score = intents.classify(text)
    assert got == "add_product", (
        f"{text!r} got {got!r} (score={score:.3f}) — should be add_product. "
        f"Likely a prototype regression in `intents.INTENT_PROTOTYPES` or "
        f"the verb tiebreaker."
    )


def test_verb_tiebreaker_does_not_override_clear_search():
    """The tiebreaker must not steamroll a clearly-classified search query."""
    got, _ = intents.classify("show me iphone under 60000")
    assert got == "search_products"
    got, _ = intents.classify("find laptops below 50000")
    assert got == "search_products"


def test_verb_tiebreaker_respects_update_and_delete():
    """`update price` and `delete product` should still win their respective
    intents — the tiebreaker is *additive*, not destructive."""
    assert intents.classify("update product 12345 to 50000")[0] == "update_product"
    assert intents.classify("delete product abc-123")[0] == "delete_product"
    assert intents.classify("remove my iPhone listing")[0] == "delete_product"
