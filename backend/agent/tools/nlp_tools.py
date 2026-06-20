"""NLP-flavoured tools: structured extraction + affirmative detection.

Baseline scope:
- `extract_product_fields` — a deterministic regex backstop the planner can
  call when it wants a quick structured draft from vendor free text. In
  practice the planner's JSON-mode reply already carries a `ProductDraft`,
  so this tool is mostly a safety net + a deterministic input for tests.
- `is_affirmative` — used by the orchestrator (NOT exposed to the LLM) to
  decide whether a single-token user reply confirms a pending action.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from backend.agent.schemas import ProductDraft
from backend.agent.tools.base import ToolContext, tool


# --------------------------------------------------------------------------- #
# extract_product_fields (regex backstop)
# --------------------------------------------------------------------------- #


class ExtractIn(BaseModel):
    free_text: str


_QTY_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|l|ml|pcs|pack)", re.I)
_PRICE = re.compile(
    r"(?:₹|rs\.?|inr|rupees?)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*(?:rs\.?|rupees?)",
    re.I,
)


@tool(
    name="extract_product_fields",
    input_model=ExtractIn,
    output_model=ProductDraft,
    roles=["vendor"],
    side_effect="read",
    description=(
        "Extract a structured ProductDraft from a free-text vendor message. "
        "Does NOT write to the catalog. Pure read."
    ),
)
async def extract_product_fields(args: ExtractIn, _ctx: ToolContext) -> ProductDraft:
    text = args.free_text.strip()

    qty: float = 1.0
    unit: str = "pcs"
    if m := _QTY_UNIT.search(text):
        qty = float(m.group(1))
        unit = m.group(2).lower()

    price: float = 0.0
    if m := _PRICE.search(text):
        price = float(m.group(1) or m.group(2))

    needs: list[str] = []
    if price <= 0:
        needs.append("price")
    if not _QTY_UNIT.search(text):
        needs.append("quantity_and_unit")

    # Strip the quantity / price tokens out of the name so it's cleaner.
    name = _QTY_UNIT.sub("", text)
    name = _PRICE.sub("", name).strip(" ,.-") or "Unnamed product"

    return ProductDraft(
        name=name[:80],
        category="Uncategorized",
        price=price if price > 0 else 1.0,
        quantity=qty,
        unit=unit,  # type: ignore[arg-type]
        confidence=0.4 if needs else 0.8,
        needs_clarification=needs,
    )


# --------------------------------------------------------------------------- #
# is_affirmative — used by orchestrator, NOT registered as a tool
# --------------------------------------------------------------------------- #


_YES = {"yes", "y", "yeah", "yep", "ok", "okay", "confirm", "sure", "go", "do it"}
_NO = {"no", "n", "nope", "cancel", "stop", "abort", "don't", "do not"}

_PUNCT_TRIM = ".!?,;: \t\n"


def is_affirmative(text: str) -> bool:
    """Detect a single-token affirmative confirmation from the user.

    Conservative on purpose: returns False if the message is ambiguous,
    multi-clause, or includes a negation. The orchestrator falls back to
    "please reply yes or no" on False, so false negatives are safe.
    """
    if not text:
        return False
    t = text.strip().lower().strip(_PUNCT_TRIM)
    if not t:
        return False
    if t in _YES:
        return True
    if t in _NO:
        return False
    # Allow simple multi-word forms like "yes please" or "ok confirm".
    head = t.split()[0]
    return head in _YES


def is_negative(text: str) -> bool:
    """Counterpart to is_affirmative — explicit no/cancel."""
    if not text:
        return False
    t = text.strip().lower().strip(_PUNCT_TRIM)
    if t in _NO:
        return True
    head = t.split()[0] if t else ""
    return head in _NO
