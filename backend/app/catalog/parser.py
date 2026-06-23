"""Deterministic (non-LLM) parser: free-text description -> catalog fields.

Feature 006 FR-4. Extracts product_name, brand, price_inr, unit_type/unit_value,
stock_quantity, and a best-effort category/subcategory from a typed or spoken
description. Pure function — no DB, no network. Category/subcategory *names* are
returned best-effort; the service resolves them to ids (falling back to the
seeded General subcategory, 006 FR-5). Missing price is left as None so the
service can reject it (005 FR-16 — price is mandatory).
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from backend.app.catalog.enums import UnitType
from backend.app.catalog.seed_data import category_names, subcategory_names

# Small known-brand vocabulary (from the 005 examples + common Indian grocery
# brands). Anything else falls back to the "Generic" sentinel (005 FR-9).
KNOWN_BRANDS = [
    "Amul",
    "Tropicana",
    "Britannia",
    "India Gate",
    "Nestle",
    "Mother Dairy",
    "Aashirvaad",
    "Tata",
    "Parle",
    "Patanjali",
]

# Numeric prices. Accept any of:
#   * `<currency>NNN[.dd]`, `NNN[.dd]<currency>` (₹, Rs, INR, rupees)
#   * `price: NNN`, `priced at NNN`, `for NNN`
#   * a bare 3+ digit integer (`45000`) — required for voice transcripts
#     that drop currency markers entirely.
# Thousands-comma separators (₹45,000 / 1,250.50) are honoured: the
# digit group accepts `NNN(,NNN)*` and the trailing decimal stays optional.
#
# Order matters: more specific (with currency / explicit "price" keyword)
# is tried before bare numbers so we don't accidentally pick up SKU-style
# digits when a real price is present.
_NUM = r"(?P<n>[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
_PRICE_RES = [
    re.compile(rf"(?:₹|rs\.?|inr|rupees?)\s*{_NUM}", re.I),
    re.compile(rf"{_NUM}\s*(?:₹|rs\.?|inr|rupees?)", re.I),
    re.compile(rf"\b(?:price|priced)\b\s*(?:at|of|is|=|:)?\s*{_NUM}", re.I),
    re.compile(rf"\bfor\b\s+{_NUM}\b", re.I),
    # Bare integer fallback. Requires ≥3 digits so SKUs like "S24" don't
    # accidentally win, AND must not be preceded by a SKU/ID/model keyword
    # (negative look-behind) so phrases like "SKU 12345" or "ID 999" are
    # treated as identifiers, not prices. Decimals are excluded from the
    # bare path because they'd grab unit values like "1.5 kg".
    re.compile(
        r"(?<!\bsku\s)(?<!\bid\s)(?<!\bmodel\s)(?<!\bserial\s)"
        r"(?<!\bpart\s)(?<!\bcode\s)(?<!\bno\s)(?<!\bno\.\s)(?<!#)"
        r"\b(?P<n>[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{3,})\b",
        re.I,
    ),
]

# unit suffix -> (UnitType)
_UNIT_RE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*"
    r"(kgs?|kilograms?|g|gm|gms|grams?|ml|millilitres?|milliliters?|l|ltr|litres?|liters?)\b",
    re.I,
)
_UNIT_MAP = {
    "kg": UnitType.KILOGRAM,
    "kgs": UnitType.KILOGRAM,
    "kilogram": UnitType.KILOGRAM,
    "kilograms": UnitType.KILOGRAM,
    "g": UnitType.GRAM,
    "gm": UnitType.GRAM,
    "gms": UnitType.GRAM,
    "gram": UnitType.GRAM,
    "grams": UnitType.GRAM,
    "ml": UnitType.MILLILITER,
    "millilitre": UnitType.MILLILITER,
    "millilitres": UnitType.MILLILITER,
    "milliliter": UnitType.MILLILITER,
    "milliliters": UnitType.MILLILITER,
    "l": UnitType.LITER,
    "ltr": UnitType.LITER,
    "litre": UnitType.LITER,
    "litres": UnitType.LITER,
    "liter": UnitType.LITER,
    "liters": UnitType.LITER,
}
# count-style units without a numeric prefix
_COUNT_RE = re.compile(r"\b(\d+)?\s*(dozen|pack|packs|piece|pieces|pcs)\b", re.I)
_COUNT_MAP = {
    "dozen": UnitType.DOZEN,
    "pack": UnitType.PACK,
    "packs": UnitType.PACK,
    "piece": UnitType.PIECE,
    "pieces": UnitType.PIECE,
    "pcs": UnitType.PIECE,
}

_STOCK_RE = re.compile(
    r"(\d+)\s*(?:in\s*stock|units?|pcs|pieces|qty|quantity|stock)", re.I
)


@dataclass
class ParsedProduct:
    description: str
    product_name: str
    brand: str = "Generic"
    price_inr: Decimal | None = None
    unit_type: UnitType = UnitType.PIECE
    unit_value: Decimal = field(default_factory=lambda: Decimal("1"))
    stock_quantity: int = 0
    category_name: str | None = None
    subcategory_name: str | None = None


def _to_price(raw: str) -> Decimal | None:
    """Parse a possibly thousands-comma-separated price string.

    `"45,000"` → `Decimal("45000.00")`, `"1,250.50"` → `Decimal("1250.50")`.
    Anything Decimal can't parse returns None so the service layer can
    reject (005 FR-16 — price is mandatory).
    """
    try:
        cleaned = raw.replace(",", "")
        return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None


def _match_name(text: str, names: list[str]) -> str | None:
    """Return the first vocabulary name that appears as a whole word in text."""
    low = text.lower()
    for name in names:
        if re.search(rf"\b{re.escape(name.lower())}\b", low):
            return name
    return None


def parse_description(text: str) -> ParsedProduct:
    raw = (text or "").strip()

    # price (mandatory downstream). Patterns are ordered most-specific
    # first; we accept the first one that yields a parseable Decimal.
    price: Decimal | None = None
    for rgx in _PRICE_RES:
        m = rgx.search(raw)
        if m:
            price = _to_price(m.group("n"))
            if price is not None:
                break

    # unit
    unit_type = UnitType.PIECE
    unit_value = Decimal("1")
    um = _UNIT_RE.search(raw)
    if um:
        unit_type = _UNIT_MAP[um.group(2).lower()]
        try:
            unit_value = Decimal(um.group(1))
        except (InvalidOperation, ValueError):
            unit_value = Decimal("1")
    else:
        cm = _COUNT_RE.search(raw)
        if cm:
            unit_type = _COUNT_MAP[cm.group(2).lower()]
            if cm.group(1):
                unit_value = Decimal(cm.group(1))

    # stock. When the vendor explicitly says "30 in stock" / "qty 5", honour
    # that number. Otherwise default to 1 so the listing is *immediately
    # purchasable* — search filters and the storefront UI treat
    # `stock_quantity == 0` as out-of-stock and hide / dim the listing,
    # which made every chat-added product look broken. A vendor can always
    # update stock later via the vendor dashboard or `update_product`.
    stock = 1
    sm = _STOCK_RE.search(raw)
    if sm:
        stock = int(sm.group(1))

    # brand
    brand = _match_name(raw, KNOWN_BRANDS) or "Generic"

    # category / subcategory (subcategory is more specific; try it first)
    subcategory_name = _match_name(raw, subcategory_names())
    category_name = _match_name(raw, category_names())

    # product name: strip the structured tokens we already consumed
    name = raw
    for rgx in _PRICE_RES:
        name = rgx.sub(" ", name)
    name = _UNIT_RE.sub(" ", name)
    name = _COUNT_RE.sub(" ", name)
    name = _STOCK_RE.sub(" ", name)
    name = re.sub(
        r"\b(in\s*stock|stock|qty|quantity|units?|price[d]?|rupees?|rs|inr)\b",
        " ",
        name,
        flags=re.I,
    )
    if category_name:
        name = re.sub(rf"\b{re.escape(category_name)}\b", " ", name, flags=re.I)
    # Strip a leading "add (a) (new) product?" preamble and trailing prepositions
    # that survive after price/unit removal. These are typical in chatbot adds
    # ("Add a new Samsung S24 for ₹45000") and voice transcripts.
    name = re.sub(
        r"^\s*(?:please\s+)?add(?:\s+(?:a|an|the))?(?:\s+new)?(?:\s+product)?\s+",
        " ",
        name,
        flags=re.I,
    )
    name = re.sub(r"\b(?:for|at|of|is|by|to)\b", " ", name, flags=re.I)
    name = re.sub(r"[,;]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip(" -.")
    if not name:
        name = "Unnamed product"

    return ParsedProduct(
        description=raw,
        product_name=name,
        brand=brand,
        price_inr=price,
        unit_type=unit_type,
        unit_value=unit_value,
        stock_quantity=stock,
        category_name=category_name,
        subcategory_name=subcategory_name,
    )
