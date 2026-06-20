"""Module-level in-memory store for the agent baseline.

This is the *only* persistence layer in the current baseline (per the round's
scope: no Postgres yet). When the process exits, the data is gone. That's
fine for the REPL demo round and for unit tests.

Hard rules:
- ONLY `agent.tools.*` imports this module. Orchestrator + planner stay
  storage-agnostic (matches `spec.md` §2.5 architectural rule 1).
- IDs are stable, monotonic strings (`p_1`, `p_2`, ..., `st_1`, ...) so that
  tests can assert exact IDs after a `reset_store()` call.
- All access goes through the small typed helpers below — never reach into
  the globals from outside this file.

When we promote to Postgres, the surface of this module becomes the surface
of a tiny repository layer that talks to SQL. Tests stay the same.
"""
from __future__ import annotations

import threading
from typing import Iterator

from backend.agent.schemas import Product, Store

# --------------------------------------------------------------------------- #
# Storage globals + lock
# --------------------------------------------------------------------------- #

_LOCK = threading.RLock()

# product_id -> Product
_PRODUCTS: dict[str, Product] = {}
# store_id -> Store
_STORES: dict[str, Store] = {}

# Monotonic counters. Reset by `reset_store()`.
_PRODUCT_COUNTER = 0
_STORE_COUNTER = 0


# --------------------------------------------------------------------------- #
# ID minting
# --------------------------------------------------------------------------- #


def next_product_id() -> str:
    global _PRODUCT_COUNTER
    with _LOCK:
        _PRODUCT_COUNTER += 1
        return f"p_{_PRODUCT_COUNTER}"


def next_store_id() -> str:
    global _STORE_COUNTER
    with _LOCK:
        _STORE_COUNTER += 1
        return f"st_{_STORE_COUNTER}"


# --------------------------------------------------------------------------- #
# Store CRUD
# --------------------------------------------------------------------------- #


def put_store(store: Store) -> Store:
    with _LOCK:
        _STORES[store.store_id] = store
        return store


def get_store(store_id: str) -> Store | None:
    return _STORES.get(store_id)


def get_or_create_default_store(*, vendor_id: str) -> Store:
    """Each vendor gets one auto-created store in the baseline.

    The full create_store / set_store_details flow is deferred (spec.md §5.6).
    For the demo round we mint a single store per vendor_id so add_product
    has somewhere to land.
    """
    with _LOCK:
        for s in _STORES.values():
            if s.vendor_id == vendor_id:
                return s
        store = Store(
            store_id=next_store_id(),
            vendor_id=vendor_id,
            name=f"{vendor_id}'s Store",
            category="General",
            region="Bangalore",
            lat=12.9716,
            lng=77.5946,
            rating=0.0,
        )
        _STORES[store.store_id] = store
        return store


# --------------------------------------------------------------------------- #
# Product CRUD
# --------------------------------------------------------------------------- #


def put_product(product: Product) -> Product:
    with _LOCK:
        _PRODUCTS[product.product_id] = product
        return product


def get_product(product_id: str) -> Product | None:
    return _PRODUCTS.get(product_id)


def iter_products() -> Iterator[Product]:
    # Snapshot under lock; iterating outside the lock is fine because Product
    # is a frozen pydantic model from the caller's point of view.
    with _LOCK:
        return iter(list(_PRODUCTS.values()))


def products_for_vendor(vendor_id: str) -> list[Product]:
    with _LOCK:
        out: list[Product] = []
        store_ids = {s.store_id for s in _STORES.values() if s.vendor_id == vendor_id}
        for p in _PRODUCTS.values():
            if p.store_id in store_ids:
                out.append(p)
        return out


# --------------------------------------------------------------------------- #
# Test helpers
# --------------------------------------------------------------------------- #


def reset_store() -> None:
    """Wipe everything. Call between tests and at the top of the REPL."""
    global _PRODUCT_COUNTER, _STORE_COUNTER
    with _LOCK:
        _PRODUCTS.clear()
        _STORES.clear()
        _PRODUCT_COUNTER = 0
        _STORE_COUNTER = 0


def snapshot() -> dict[str, int]:
    """Cheap summary for debug logs / CLI `/dump` command."""
    return {
        "products": len(_PRODUCTS),
        "stores": len(_STORES),
    }
