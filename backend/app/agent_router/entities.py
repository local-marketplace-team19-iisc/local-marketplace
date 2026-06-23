"""Deterministic entity extractors used by the SBERT router.

Spec FR-3 — "Entity extraction MUST be deterministic and LLM-free." So this
module is regex + token-rule + a single optional SBERT call for the
category-name match. No LLM in the request path.

Public surface (one function per slot the router fills):
    extract_price(text)        → float | None      ₹/Rs/INR forms + k-suffix
    extract_max_price(text)    → float | None      "under ₹60000", "below 1k"
    extract_min_price(text)    → float | None      "above ₹500"
    extract_product_id(text)   → str | None        "product 12345", "#12345", UUID
    extract_keywords(text, intent) → str           the residue after strip
    extract_category(text)     → (name, score) | None   SBERT match

The price extractor uses a regex / scoring strategy parallel to (but
independent of) feature 006's `catalog/parser.py`. The two could share a
utility module if a v2 refactor consolidates them; today they intentionally
live in their own feature trees to keep import graphs simple.
"""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # no public types to expose; keeps the at-import graph clean


# --------------------------------------------------------------------------- #
# Price-shaped numerics
# --------------------------------------------------------------------------- #


_PRICE_RE = re.compile(
    r"""
    (?:₹|rs\.?|inr)?
    \s*
    (\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)     # comma-thousands OR plain (both allow .dd)
    \s*
    (k|K)?
    \s*
    (?:inr|rs\.?|₹)?
    """,
    re.VERBOSE | re.IGNORECASE,
)

_CURRENCY_RE = re.compile(r"₹|rs\.?|inr", re.IGNORECASE)


def _all_price_candidates(text: str) -> list[tuple[int, float, int, int]]:
    """Find every plausible price in `text`.

    Returns a list of `(score, value, match_start, match_end)`. Higher scores
    are more confident prices. The router uses the *start position* of the
    match plus the words right before it ("under", "below", "above") to bind
    a value to `max_price` or `min_price`.
    """
    out: list[tuple[int, float, int, int]] = []
    for m in _PRICE_RE.finditer(text):
        digits, k_suffix = m.group(1), m.group(2)
        raw = digits.replace(",", "")
        try:
            value = float(raw)
        except ValueError:  # pragma: no cover — regex guards
            continue
        if k_suffix:
            value *= 1000
        if value <= 0:
            continue

        # Compute the position of the first digit inside the regex match
        # (the match itself can include a leading space and/or currency
        # marker we want to discount when judging "glued to a letter").
        match_str = m.group(0)
        digit_offset = next(
            (i for i, ch in enumerate(match_str) if ch.isdigit()), 0
        )
        digit_start = m.start() + digit_offset

        window_before = text[max(0, digit_start - 4) : digit_start]
        window_after = text[m.end() : m.end() + 4]
        has_currency = bool(
            _CURRENCY_RE.search(window_before)
            or _CURRENCY_RE.search(window_after)
            or _CURRENCY_RE.search(match_str)
        )

        # "S24" / "iPhone15": digits with a letter *directly* before with no
        # space and no currency in sight. We check only the single char
        # immediately preceding the first digit and the one immediately
        # after the last digit.
        char_before = text[digit_start - 1] if digit_start > 0 else ""
        char_after = text[m.end()] if m.end() < len(text) else ""
        # Trim trailing 'k' from match before the after-char check so
        # "50k" doesn't see 'k' as a glue letter.
        glued_to_letter = (char_before.isalpha() and not char_before.isspace()) or (
            char_after.isalpha() and not k_suffix
        )
        if glued_to_letter and not has_currency:
            continue

        score = 0
        if has_currency:
            score += 2
        if k_suffix:
            score += 1
        if "," in digits:
            score += 1

        # A bare integer with no currency/comma/k signal is only acceptable
        # as a price when it's large enough that "iPhone 15" / "S24"-style
        # model numbers can't be mistaken for it. The threshold mirrors what
        # the audience would type as a real price (≥ 100 covers ₹100 → ₹∞).
        if score == 0 and value < 100:
            continue

        out.append((score, value, m.start(), m.end()))
    return out


def extract_price(text: str) -> Optional[float]:
    """Return the most plausible single price (e.g. for `add_product`)."""
    candidates = _all_price_candidates(text or "")
    if not candidates:
        return None
    candidates.sort(key=lambda x: (-x[0], -x[1]))
    return candidates[0][1]


_MAX_KEYWORDS = ("under", "below", "less than", "max", "maximum", "upto", "up to", "<=", "<")
_MIN_KEYWORDS = ("above", "over", "more than", "min", "minimum", "atleast", "at least", ">=", ">")


def _price_with_modifier(text: str, keywords: tuple[str, ...]) -> Optional[float]:
    """Return the price following one of `keywords`. Used by max/min extractors.

    Strategy: for each candidate price, look back ~16 chars from its start
    for any of the modifier keywords; if found, this is our value. If no
    modifier-tagged candidate is found, return None — even if the text has
    a price, we cannot bind it to max/min without an explicit modifier.
    """
    if not text:
        return None
    lower = text.lower()
    for score, value, start, _end in sorted(
        _all_price_candidates(text), key=lambda x: (-x[0], -x[1])
    ):
        window = lower[max(0, start - 16) : start]
        if any(kw in window for kw in keywords):
            return value
    return None


def extract_max_price(text: str) -> Optional[float]:
    """Parse 'under ₹60,000' / 'below 1k' / 'less than 500'."""
    return _price_with_modifier(text, _MAX_KEYWORDS)


def extract_min_price(text: str) -> Optional[float]:
    """Parse 'above ₹500' / 'over 1000' / 'more than 250'."""
    return _price_with_modifier(text, _MIN_KEYWORDS)


# --------------------------------------------------------------------------- #
# Product identifier
# --------------------------------------------------------------------------- #


_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_LABELLED_ID_RE = re.compile(
    r"(?:product[\s_-]*id|product|item|id|#)\s*[:=#\-_]?\s*([A-Za-z0-9][A-Za-z0-9-]*)",
    re.IGNORECASE,
)


def extract_product_id(text: str) -> Optional[str]:
    """Pull a product id out of `text`.

    Priority:
      1. Any full UUID in the text wins (highest specificity).
      2. Otherwise the token after a label like 'id', '#', 'product', 'item'.
      3. None — the router will fall back to vendor-scoped name lookup.
    """
    if not text:
        return None
    m = _UUID_RE.search(text)
    if m:
        return m.group(0)
    m = _LABELLED_ID_RE.search(text)
    if m:
        candidate = m.group(1).strip(".,!?")
        # Heuristic guard: ignore the words "the", "my", "your" etc. that the
        # label regex can otherwise capture as if they were identifiers.
        if candidate.lower() in {"the", "my", "your", "a", "an", "this", "that"}:
            return None
        return candidate
    return None


# --------------------------------------------------------------------------- #
# Keywords (the residue for search-products `q`)
# --------------------------------------------------------------------------- #


_INTENT_VERBS: dict[str, set[str]] = {
    "search_products": {
        "show",
        "find",
        "search",
        "look",
        "for",
        "me",
        "any",
        "do",
        "you",
        "have",
        "buy",
        "want",
        "to",
        "i",
    },
    "add_product": {
        "add",
        "new",
        "create",
        "list",
        "register",
        "put",
        "up",
        "this",
        "for",
        "a",
        "priced",
    },
    "update_product": {
        "update",
        "change",
        "edit",
        "modify",
        "set",
        "the",
        "of",
        "to",
        "price",
        "stock",
        "product",
        "item",
    },
    "delete_product": {
        "delete",
        "remove",
        "take",
        "down",
        "the",
        "listing",
        "from",
        "store",
        "product",
        "item",
    },
    "get_my_listings": {"show", "list", "what", "my", "i", "have", "selling", "products"},
    "get_categories": {
        "what",
        "categories",
        "category",
        "kinds",
        "show",
        "list",
        "available",
        "supported",
    },
    "unknown": set(),
}

_STOPWORDS = {
    "a",
    "an",
    "the",
    "of",
    "in",
    "on",
    "at",
    "to",
    "from",
    "with",
    "and",
    "or",
    "near",
    "me",
    "my",
    "your",
    "please",
    "for",
    "by",
    "is",
    "are",
    "listing",
    "listings",
}

_PRICE_MODIFIERS = set(_MAX_KEYWORDS) | set(_MIN_KEYWORDS)


def extract_keywords(text: str, intent: str) -> str:
    """Strip intent verbs + stop-words + the *selected* price; return the residue.

    Used as `q` for `search_products` ("Show me iPhone 15 under ₹60,000" →
    "iphone 15"). Also useful for `update_product` when no explicit product
    id is present. Lower-cased.

    We mask only the **highest-scoring** price candidate (the actual price)
    rather than every price-shaped digit run. This preserves model numbers
    like "15" in "iPhone 15" and ids like "12345" in "product 12345" even
    though both look numeric to a naive regex.
    """
    if not text:
        return ""
    verbs = _INTENT_VERBS.get(intent, set())
    drop = verbs | _STOPWORDS | _PRICE_MODIFIERS | {"₹", "rs", "rs.", "inr"}

    # Identify the *winning* price candidate (if any) and blank its span.
    # Any candidate that passed `_all_price_candidates`'s anti-model-number
    # filter is good enough to remove from the keyword bag — it's already
    # been gated against "iPhone 15"/"S24" by the time it reaches us.
    candidates = _all_price_candidates(text)
    masked_text = text
    if candidates:
        candidates.sort(key=lambda x: (-x[0], -x[1]))
        _score, _value, start, end = candidates[0]
        masked_text = text[:start] + (" " * (end - start)) + text[end:]

    out: list[str] = []
    for tok in masked_text.split():
        norm = tok.lower().strip(".,!?")
        if not norm:
            continue
        if norm in drop:
            continue
        # drop tiny standalone integers that the price logic didn't catch
        if norm.isdigit() and int(norm) <= 10:
            continue
        out.append(norm)
    return " ".join(out)


# --------------------------------------------------------------------------- #
# Category — optional SBERT match against seeded category names
# --------------------------------------------------------------------------- #


def extract_category(text: str) -> Optional[tuple[str, float]]:
    """Return `(category_name, score)` of the best SBERT match in `text`, or None.

    Loads SBERT lazily so the rest of this module is import-free. Only
    returns a hit above `settings.CATEGORY_MATCH_THRESHOLD`.
    """
    if not text or not text.strip():
        return None

    # Lazy imports to keep the module testable without sentence-transformers
    # in environments where only the regex extractors are exercised.
    import numpy as np

    from backend.app.agent_router.sbert import get_sbert_model
    from backend.app.core.config import settings
    from backend.app.db.session import SessionLocal
    from backend.app.services import product_service

    db = SessionLocal()
    try:
        categories = [
            c.category_name
            for c in product_service.list_categories(db)
            if c.category_name
        ]
    finally:
        db.close()
    if not categories:
        return None

    model = get_sbert_model()
    cat_vecs = model.encode(categories, normalize_embeddings=True, convert_to_numpy=True)
    query_vec = model.encode(
        [text.strip()], normalize_embeddings=True, convert_to_numpy=True
    )[0]
    scores = cat_vecs @ query_vec
    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    if best_score < settings.CATEGORY_MATCH_THRESHOLD:
        return None
    return categories[best_idx], best_score
