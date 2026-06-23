"""Intent classifier — SBERT cosine similarity + imperative-verb tiebreaker.

The classifier has two layers (spec FR-2 "deterministic regex + SBERT"):

1. **SBERT prototype match.** `INTENT_PROTOTYPES` lists ≥3 paraphrases per
   labelled intent. These are embedded once at startup; every inbound
   utterance is embedded at request time and compared with cosine
   similarity. The highest-scoring intent wins **if** its score is above
   `settings.INTENT_CONFIDENCE_THRESHOLD`.

2. **Imperative-verb tiebreaker.** Real-world vendor utterances are often
   terse (`"Add Pixel 9 55000"`) — short enough that SBERT cannot reliably
   distinguish them from same-shape utterances in other intents. When SBERT
   is below threshold *or* the margin between the top two intents is thin,
   we consult `_VERB_HINTS` for the leading verb. If the verb is one of
   our strong action verbs (`add`, `list`, `update`, `delete`, …) the
   verb wins. This is deterministic, fast, and never leaks specific
   product names into prototypes — keeping SBERT honest.

Labels are the spec FR-1 set: six labelled intents plus the `unknown` fallback.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from backend.app.core.config import settings

if TYPE_CHECKING:
    import numpy as np  # noqa: F401


# --------------------------------------------------------------------------- #
# Prototypes — frozen at module import time
# --------------------------------------------------------------------------- #


# Prototypes encode the *action shape* of each intent, not specific products
# or prices. Mixing product names ("iphone") or numbers ("50000") into a
# prototype causes SBERT to over-fit to those tokens — e.g. `"change the
# price of my iphone to 50000"` previously caused *every* "iphone … 50000"
# utterance, including pure adds, to land on `update_product`.
# Each list intentionally uses generic placeholders ("this", "an item",
# "the listing") so the classifier learns the verb, not the noun.
INTENT_PROTOTYPES: dict[str, list[str]] = {
    "search_products": [
        "show me products",
        "find me something",
        "search for an item",
        "i want to buy something",
        "look for products near me",
        "do you have any of these",
        "show me products under a price",
        "find cheap items below a price",
        "list products under a budget",
        "search the catalog",
        "i need to find a product",
    ],
    "add_product": [
        "add a new product",
        "add this product",
        "add this item to my store",
        "create a new listing",
        "create a listing for this",
        "i want to list a new item for sale",
        "register a new product in my store",
        "put up a new listing",
        "add this to my inventory",
        "list a new item for sale",
        "post a new product",
        "sell a new item",
        "i want to sell this",
        "add product for price",
        # Terse forms (vendors and ASR transcripts both produce these). Generic
        # placeholders only — never include brand names like "iphone" or
        # specific numbers, or the classifier will over-fit and pull search /
        # update queries into add_product.
        "add item",
        "add item for price",
        "add product for amount",
        "add new item at price",
        "list item for amount",
        "list a new item for price",
        "post item at price",
        "register item at price",
        "add this for amount",
    ],
    "update_product": [
        "update the price of an existing product",
        "change the price of this listing",
        "edit my existing product",
        "modify the stock of an item",
        "set a new price for an existing product",
        "update product details",
        "change the price to a new value",
        "update an existing listing",
        "edit the listing price",
    ],
    "delete_product": [
        "delete a product",
        "remove an item from my store",
        "take down a listing",
        "remove a listing from my inventory",
        "delete my listing",
        "discontinue a product",
        "stop selling this item",
        "drop this product",
    ],
    "get_my_listings": [
        "show my listings",
        "what products do i have",
        "list my inventory",
        "show me my own products",
        "what am i selling",
        "view my own listings",
        "my catalog",
    ],
    "get_categories": [
        "what categories do you have",
        "list the categories",
        "show me the product categories",
        "what kinds of products do you sell",
        "what categories are available",
        "list category options",
    ],
}


LABELS = list(INTENT_PROTOTYPES.keys())


# Imperative-verb tiebreaker. Order matters: the regex picks the first match,
# so the verb has to be at the start of the utterance (modulo a polite
# preamble like "please" / "i want to" / "can you"). Verbs are intentionally
# narrow — no nouns, no products — so the tiebreaker is deterministic.
_VERB_HINTS: dict[str, str] = {
    # add / list a new product
    r"add": "add_product",
    r"create": "add_product",
    r"post": "add_product",
    r"register": "add_product",
    r"sell": "add_product",
    # update / change an existing one
    r"update": "update_product",
    r"change": "update_product",
    r"edit": "update_product",
    r"modify": "update_product",
    r"set": "update_product",
    # delete / remove
    r"delete": "delete_product",
    r"remove": "delete_product",
    r"discontinue": "delete_product",
    r"drop": "delete_product",
    r"take\s+down": "delete_product",
    # search
    r"find": "search_products",
    r"search": "search_products",
    r"look\s+for": "search_products",
    r"browse": "search_products",
    # my listings
    r"list\s+my": "get_my_listings",
    r"show\s+my": "get_my_listings",
    r"my\s+listings": "get_my_listings",
    r"what\s+am\s+i\s+selling": "get_my_listings",
    # categories
    r"what\s+categor": "get_categories",
    r"which\s+categor": "get_categories",
    r"list\s+categor": "get_categories",
    # generic "list X for Y" / "list a new X" — ambiguous between add and
    # listings; we use the presence of "for|at|price" later to disambiguate
    r"list": "add_product",
}

# Match a leading polite preamble + first verb. We capture the verb so the
# rest of the message (the product+price) doesn't pollute it.
_VERB_PREFIX_RE = re.compile(
    r"^\s*(?:please\s+|kindly\s+|can\s+you\s+|could\s+you\s+|i\s+want\s+to\s+|"
    r"i\s+would\s+like\s+to\s+|i'd\s+like\s+to\s+|let\s+me\s+|please\s+|"
    r"hey\s+|hi\s+|hello\s+)?",
    re.I,
)


def _verb_hint(text: str) -> str | None:
    """Return the intent suggested by the leading imperative verb, or None.

    Strips a polite preamble and tries each `_VERB_HINTS` regex anchored at
    the (now-cleaned) start of the utterance. First match wins. We require
    the verb to be at the start so a query like `"show me the iphone delete
    option"` doesn't get flagged as delete.
    """
    if not text:
        return None
    cleaned = _VERB_PREFIX_RE.sub("", text.strip(), count=1).lstrip()
    for pattern, label in _VERB_HINTS.items():
        if re.match(rf"{pattern}\b", cleaned, flags=re.I):
            return label
    return None


# --------------------------------------------------------------------------- #
# Index — embeddings matrix + label vector, built lazily on first call
# --------------------------------------------------------------------------- #


@dataclass
class IntentIndex:
    """Materialised prototype embeddings + their labels.

    `prototypes` is an (N, D) float32 array of L2-normalised SBERT
    embeddings; `labels` is a parallel list of length N mapping each row
    back to its intent label. Cosine similarity reduces to a dot product
    because we L2-normalise on both sides.
    """

    prototypes: "np.ndarray"  # type: ignore[name-defined]
    labels: list[str]


@lru_cache(maxsize=1)
def get_intent_index() -> IntentIndex:
    """Build (or return cached) prototype-embedding index."""
    import numpy as np

    from backend.app.agent_router.sbert import get_sbert_model

    model = get_sbert_model()
    texts: list[str] = []
    labels: list[str] = []
    for label, paraphrases in INTENT_PROTOTYPES.items():
        for p in paraphrases:
            texts.append(p)
            labels.append(label)
    embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return IntentIndex(prototypes=np.asarray(embeddings, dtype=np.float32), labels=labels)


def reset_intent_index_cache() -> None:
    """Test-only: drop the cached index so the next call re-builds it."""
    get_intent_index.cache_clear()


# --------------------------------------------------------------------------- #
# Public classify(...) — the one entry point the router uses
# --------------------------------------------------------------------------- #


def classify(text: str) -> tuple[str, float]:
    """Classify `text` into one of the labelled intents (or `unknown`).

    Returns a `(label, score)` tuple where `score` is the cosine similarity
    of `text` against the **best-matching prototype** (not an average over
    the intent's prototypes). Below `INTENT_CONFIDENCE_THRESHOLD` the label
    is forced to `"unknown"` *and* the original best-score is returned so
    callers can log it for prototype tuning.

    Two cases trigger the verb-prefix tiebreaker (FR-2 deterministic +
    SBERT):
      * SBERT is below the confidence threshold → if the utterance starts
        with a strong action verb we believe the verb, not SBERT.
      * SBERT is above threshold but the verb disagrees with the top label
        AND the margin to the verb-suggested intent is < 0.05 → defer to
        the verb. (Stops short, terse adds being pulled into update by a
        one-prototype margin.)
    """
    import numpy as np

    from backend.app.agent_router.sbert import get_sbert_model

    cleaned = (text or "").strip()
    if not cleaned:
        return "unknown", 0.0

    model = get_sbert_model()
    query_vec = model.encode([cleaned], normalize_embeddings=True, convert_to_numpy=True)[0]
    index = get_intent_index()
    scores = index.prototypes @ query_vec  # (N,) — cosine because both sides L2-normed
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    best_label = index.labels[best_idx]

    verb_label = _verb_hint(cleaned)

    if best_score < settings.INTENT_CONFIDENCE_THRESHOLD:
        if verb_label is not None:
            # SBERT is uncertain but the verb is unambiguous. Trust the verb.
            return verb_label, best_score
        return "unknown", best_score

    # SBERT is confident. But if the verb hint disagrees, check the margin
    # to the highest-scoring prototype of the verb's intent. Within 0.05 we
    # let the verb break the tie — handles "add iPhone 50000" beating
    # update_product by a sliver.
    if verb_label is not None and verb_label != best_label:
        verb_mask = np.asarray([lbl == verb_label for lbl in index.labels])
        if verb_mask.any():
            verb_best = float(scores[verb_mask].max())
            if best_score - verb_best < 0.05:
                return verb_label, verb_best
    return best_label, best_score
