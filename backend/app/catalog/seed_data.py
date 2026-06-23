"""Seeded catalog taxonomy — the single source of categories/subcategories.

Used by the Alembic `0004` migration (to `bulk_insert` the rows on Postgres) and
by the tests (to seed an in-memory SQLite DB), so the runtime and the tests share
exactly one taxonomy definition (feature 006 FR-7).

Derived from the Feature 005 spec examples (Dairy→Milk, Beverages→Juices,
Bakery→Bread, Staples→Rice) plus the frontend `PRODUCT_CATEGORIES` list, with a
`General` subcategory under every category and a top-level `General → General`
fallback for products whose category cannot be recognized (006 FR-5).

IDs are derived deterministically with uuid5 so the migration and the tests agree
without hand-maintaining UUID literals.
"""

import uuid

# Fixed namespace so generated UUIDs are stable across runs/environments.
_NAMESPACE = uuid.UUID("6e0f1d2c-0006-5a7b-9c1d-000000000000")

GENERAL_CATEGORY_NAME = "General"
GENERAL_SUBCATEGORY_NAME = "General"

# category_name -> named subcategories (a "General" subcategory is added to each).
TAXONOMY: dict[str, list[str]] = {
    "General": [],
    "Groceries": [],
    "Vegetables": [],
    "Fruits": [],
    "Dairy": ["Milk"],
    "Bakery": ["Bread"],
    "Beverages": ["Juices"],
    "Household": [],
    "Personal Care": [],
    "Electronics": [],
    "Stationery": [],
    "Staples": ["Rice"],
}


def category_id(category_name: str) -> str:
    """Stable category UUID for a category name."""
    return str(uuid.uuid5(_NAMESPACE, f"category:{category_name}"))


def subcategory_id(category_name: str, subcategory_name: str) -> str:
    """Stable subcategory UUID for a (category, subcategory) pair."""
    return str(uuid.uuid5(_NAMESPACE, f"subcategory:{category_name}:{subcategory_name}"))


GENERAL_CATEGORY_ID = category_id(GENERAL_CATEGORY_NAME)
GENERAL_SUBCATEGORY_ID = subcategory_id(GENERAL_CATEGORY_NAME, GENERAL_SUBCATEGORY_NAME)


def iter_categories() -> list[dict]:
    """All category rows (parent is always null — 005 FR-2)."""
    return [
        {"category_id": category_id(name), "category_name": name, "parent_category_id": None}
        for name in TAXONOMY
    ]


def iter_subcategories() -> list[dict]:
    """All subcategory rows; every category gets a `General` subcategory."""
    rows: list[dict] = []
    for cat, subs in TAXONOMY.items():
        names = list(subs)
        if GENERAL_SUBCATEGORY_NAME not in names:
            names.append(GENERAL_SUBCATEGORY_NAME)
        for sub in names:
            rows.append(
                {
                    "subcategory_id": subcategory_id(cat, sub),
                    "subcategory_name": sub,
                    "parent_category_id": category_id(cat),
                    "subcategory_description": f"{sub} under {cat}",
                }
            )
    return rows


def category_names() -> list[str]:
    """All category names (for the parser's keyword vocabulary)."""
    return list(TAXONOMY.keys())


def subcategory_names() -> list[str]:
    """Distinct named subcategories excluding the generic `General` fallback."""
    names: list[str] = []
    for subs in TAXONOMY.values():
        for sub in subs:
            if sub not in names:
                names.append(sub)
    return names
