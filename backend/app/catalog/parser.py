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

# number (optionally decimal) preceded/followed by a currency marker
_PRICE_RES = [
    re.compile(r"(?:₹|rs\.?|inr|rupees?)\s*([0-9]+(?:\.[0-9]{1,2})?)", re.I),
    re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)\s*(?:₹|rs\.?|inr|rupees?)", re.I),
    re.compile(r"\bprice\b\s*[:=]?\s*([0-9]+(?:\.[0-9]{1,2})?)", re.I),
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
    try:
        return Decimal(raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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

    # price (mandatory downstream)
    price: Decimal | None = None
    for rgx in _PRICE_RES:
        m = rgx.search(raw)
        if m:
            price = _to_price(m.group(1))
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

    # stock
    stock = 0
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
        r"\b(in\s*stock|stock|qty|quantity|units?|price|rupees?|rs|inr)\b", " ", name, flags=re.I
    )
    if category_name:
        name = re.sub(rf"\b{re.escape(category_name)}\b", " ", name, flags=re.I)
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
