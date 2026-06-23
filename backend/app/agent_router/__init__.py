"""Feature 008 — lightweight SBERT-driven intent router.

Sub-modules are imported explicitly by their consumers (no `__init__.py`
re-exports) so that loading just one piece (e.g. the entity extractor in a
test) does not pay the cost of pulling in `sentence-transformers`. The
expensive bits (model load, prototype-matrix construction) live behind
`lru_cache(1)` singletons in `sbert.py` and `intents.py` respectively, and are
warmed once by the FastAPI startup hook in `backend.app.main`.
"""
