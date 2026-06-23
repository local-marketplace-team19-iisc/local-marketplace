"""Regression tests for the semantic search API (feature 008).

Coverage
--------
test_import_isolation            — search route loads without pulling bcrypt/jose
test_whitespace_validation       — Pydantic rejects empty/whitespace queries, strips valid ones
test_out_of_stock_exclusion      — stock <= 0 rows are filtered at the SQL layer, never scored
test_relevance_ranking           — results arrive in descending relevance_score order
test_pagination_boundaries       — limit/offset slicing is exact and total is stable
test_orm_relationship_resolution — category, subcategory, and vendor resolve via ORM joins

Fixture design
--------------
`db_session` uses sqlite:///:memory: with StaticPool so that every call to
engine.connect() returns the same underlying connection — all code under
test reads the seeded rows without a second round of inserts per test.
Function scope (pytest default) means each test receives a fresh, isolated
database with its own seed, preventing test-order dependencies.
"""

import importlib.util
import sys
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.models  # noqa: F401 — registers every ORM class with Base
from backend.app.db.session import Base
from backend.app.models.category import Category
from backend.app.models.product import Product
from backend.app.models.subcategory import SubCategory
from backend.app.models.user import User, UserRole
from backend.app.models.vendor import Vendor
from backend.app.schemas.search import SearchRequest
from backend.app.services.search_service import SearchValidationError, search_products


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Spin up an isolated in-memory SQLite database seeded with four products.

    Seed layout
    -----------
    Category   : Groceries
    SubCategory: Staples  (parent → Groceries)
    Vendor     : Super Store  (lat 12.97, lon 77.59)

    Products (all same vendor / subcategory)
    ─────────────────────────────────────────────────────────────────────
    Name                         Brand        stock  role in tests
    ─────────────────────────────────────────────────────────────────────
    Tata Salt                    Tata         10     positive match
    India Gate Basmati Rice      India Gate    5     positive match + top rank
    Britannia Whole Wheat Bread  Britannia     3     positive match
    Amul Full Cream Milk         Amul          0     out-of-stock control
    ─────────────────────────────────────────────────────────────────────
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,   # all sessions share the same in-memory connection
        echo=False,
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine)
    db = SessionFactory()

    # ── taxonomy ─────────────────────────────────────────────────────────────
    cat_id = str(uuid.uuid4())
    sub_id = str(uuid.uuid4())
    db.add(Category(
        category_id=cat_id,
        category_name="Groceries",
    ))
    db.add(SubCategory(
        subcategory_id=sub_id,
        subcategory_name="Staples",
        parent_category_id=cat_id,
        subcategory_description="Rice, wheat, dal, salt and other staples.",
    ))
    db.flush()

    # ── vendor ───────────────────────────────────────────────────────────────
    user_id   = str(uuid.uuid4())
    vendor_id = str(uuid.uuid4())
    db.add(User(
        id=user_id, email="vendor@test.com",
        password_hash="x", role=UserRole.vendor.value,
    ))
    db.flush()
    db.add(Vendor(
        id=vendor_id, user_id=user_id, shop_name="Super Store",
        shop_location_lat=12.97, shop_location_lon=77.59,
    ))
    db.flush()

    # ── product factory ───────────────────────────────────────────────────────
    def _product(name: str, brand: str, description: str, stock: int) -> Product:
        return Product(
            product_id=str(uuid.uuid4()),
            subcategory_id=sub_id,
            product_name=name,
            brand=brand,
            description=description,
            unit_type="PIECE",
            unit_value="1.000",
            price_inr="50.00",
            vendor_id=vendor_id,
            stock_quantity=stock,
        )

    db.add(_product(
        "Tata Salt", "Tata",
        "1 kg pure iodised salt for everyday cooking",
        stock=10,
    ))
    db.add(_product(
        "India Gate Basmati Rice", "India Gate",
        "5 kg premium long grain basmati rice",
        stock=5,
    ))
    db.add(_product(
        "Britannia Whole Wheat Bread", "Britannia",
        "soft whole wheat bread loaf for sandwiches",
        stock=3,
    ))
    db.add(_product(
        "Amul Full Cream Milk", "Amul",
        "1 L full cream milk tetra pack",
        stock=0,                            # ← out-of-stock control
    ))
    db.commit()

    yield db
    db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestImportIsolation:
    """Loading the search route must not introduce bcrypt or jose at module load time."""

    def test_import_isolation(self):
        """Dynamically load routes/search.py and verify the load-time module graph.

        Strategy
        --------
        1. Snapshot which bcrypt/jose keys exist in sys.modules BEFORE loading.
        2. Load search.py via importlib (bypassing routes/__init__.py which
           imports auth → bcrypt).
        3. Assert no new bcrypt or jose keys were added by the load.

        This test is position-independent: it uses a delta check so it passes
        even when pytest has already imported other modules earlier in the run.
        """
        route_key = "backend.app.api.routes.search"

        # Evict any cached copy to force a fresh module execution.
        cached = sys.modules.pop(route_key, None)

        bcrypt_before = frozenset(k for k in sys.modules if "bcrypt" in k)
        jose_before   = frozenset(k for k in sys.modules if "jose"   in k)

        spec = importlib.util.spec_from_file_location(
            route_key,
            "backend/app/api/routes/search.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[route_key] = mod
        spec.loader.exec_module(mod)

        new_bcrypt = frozenset(k for k in sys.modules if "bcrypt" in k) - bcrypt_before
        new_jose   = frozenset(k for k in sys.modules if "jose"   in k) - jose_before

        assert not new_bcrypt, (
            f"Loading search.py introduced bcrypt into sys.modules: {new_bcrypt}"
        )
        assert not new_jose, (
            f"Loading search.py introduced jose into sys.modules: {new_jose}"
        )

        # Verify the router itself was registered correctly.
        route_paths = {r.path: list(r.methods) for r in mod.router.routes}
        assert "" in route_paths,       f"Expected POST '' route, got: {route_paths}"
        assert "POST" in route_paths[""], f"Expected POST method, got: {route_paths}"

        # Restore state so later tests that may reference the cached module work.
        if cached is not None:
            sys.modules[route_key] = cached


class TestSchemaValidation:
    """SearchRequest Pydantic validation rules."""

    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            SearchRequest(q="")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("q",) for e in errors), (
            f"Expected error on field 'q', got: {errors}"
        )

    def test_whitespace_only_rejected(self):
        """A single space or multi-space string must not pass as a valid query."""
        for bad_query in ("   ", "\t", "\n", "  \t  "):
            with pytest.raises(ValidationError, match="whitespace"):
                SearchRequest(q=bad_query)

    def test_leading_trailing_whitespace_stripped(self):
        """Valid queries with surrounding whitespace are cleaned in-place."""
        req = SearchRequest(q="  basmati rice  ")
        assert req.q == "basmati rice", (
            f"Expected stripped value, got: {req.q!r}"
        )

    def test_limit_above_50_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(q="salt", limit=51)

    def test_limit_of_50_accepted(self):
        req = SearchRequest(q="salt", limit=50)
        assert req.limit == 50

    def test_negative_offset_rejected(self):
        with pytest.raises(ValidationError):
            SearchRequest(q="salt", offset=-1)

    def test_zero_offset_accepted(self):
        req = SearchRequest(q="salt", offset=0)
        assert req.offset == 0

    def test_defaults_are_correct(self):
        req = SearchRequest(q="salt")
        assert req.limit == 10
        assert req.offset == 0


class TestOutOfStockExclusion:
    """Products with stock_quantity <= 0 must never appear in any result page."""

    def test_oos_product_absent_from_direct_match(self, db_session):
        """Querying tokens exclusive to the OOS product returns zero results."""
        # "amul" and "cream" appear only in "Amul Full Cream Milk" (stock=0)
        result = search_products(db_session, query="amul full cream milk", limit=10, offset=0)

        names = [item.product_name for item in result.results]
        assert "Amul Full Cream Milk" not in names, (
            f"Out-of-stock product leaked into results: {names}"
        )
        assert result.total == 0, (
            f"Expected total=0 for OOS-only query, got total={result.total}"
        )

    def test_stock_invariant_on_broad_query(self, db_session):
        """Every item in any result page must have stock_quantity > 0."""
        result = search_products(
            db_session,
            query="salt rice bread milk",   # covers all 4 products
            limit=50, offset=0,
        )
        for item in result.results:
            assert item.stock_quantity > 0, (
                f"Item with stock={item.stock_quantity} appeared: {item.product_name}"
            )

    def test_total_excludes_oos_from_count(self, db_session):
        """total must count only in-stock matches, not OOS products."""
        result = search_products(
            db_session,
            query="salt rice bread milk",
            limit=50, offset=0,
        )
        # Fixture has 3 in-stock products that match broad query; milk is OOS
        assert result.total == 3, (
            f"Expected total=3 (3 in-stock matches), got total={result.total}"
        )

    def test_service_validates_empty_query(self, db_session):
        """Service-layer guard raises SearchValidationError on blank queries."""
        with pytest.raises(SearchValidationError):
            search_products(db_session, query="   ", limit=10, offset=0)


class TestRelevanceRanking:
    """Scores must be non-increasing and within [0.0, 1.0]."""

    def test_scores_are_descending(self, db_session):
        """Result list must be sorted by relevance_score descending."""
        result = search_products(
            db_session,
            query="basmati rice bread salt",
            limit=50, offset=0,
        )
        scores = [item.relevance_score for item in result.results]
        assert scores == sorted(scores, reverse=True), (
            f"Scores are not in descending order: {scores}"
        )

    def test_scores_are_within_unit_range(self, db_session):
        """Every relevance_score must be in [0.0, 1.0] (unit-vector cosine bound)."""
        result = search_products(
            db_session,
            query="basmati rice bread salt",
            limit=50, offset=0,
        )
        for item in result.results:
            assert 0.0 <= item.relevance_score <= 1.0, (
                f"Score out of [0,1]: {item.relevance_score} for {item.product_name}"
            )

    def test_zero_similarity_products_excluded(self, db_session):
        """Products with no token overlap with the query must not appear."""
        result = search_products(db_session, query="zzxxyy999ggg", limit=10, offset=0)
        assert result.results == []
        assert result.total == 0

    def test_top_ranked_product_matches_most_query_tokens(self, db_session):
        """A product matching multiple query tokens should rank above single-token matches.

        Query 'basmati rice' hits India Gate Basmati Rice on both 'basmati'
        AND 'rice', while Tata Salt matches zero tokens.  India Gate must
        rank first.
        """
        result = search_products(
            db_session,
            query="basmati rice",
            limit=10, offset=0,
        )
        assert len(result.results) >= 1
        assert result.results[0].product_name == "India Gate Basmati Rice", (
            f"Expected India Gate Basmati Rice at rank 1, got: "
            f"{result.results[0].product_name}"
        )

    def test_exact_single_token_match_returns_correct_product(self, db_session):
        """Querying a token exclusive to one product returns exactly that product."""
        result = search_products(db_session, query="iodised", limit=10, offset=0)
        # "iodised" is only in Tata Salt's description
        assert len(result.results) == 1
        assert result.results[0].product_name == "Tata Salt"


class TestPaginationBoundaries:
    """limit and offset must slice the ranked list precisely."""

    def test_limit_1_returns_single_result(self, db_session):
        result = search_products(
            db_session, query="salt rice bread", limit=1, offset=0,
        )
        assert len(result.results) == 1

    def test_total_is_independent_of_limit(self, db_session):
        """total reports full match count regardless of the page size requested."""
        full   = search_products(db_session, query="salt rice bread", limit=50, offset=0)
        paged  = search_products(db_session, query="salt rice bread", limit=1,  offset=0)
        assert paged.total == full.total

    def test_offset_1_skips_top_result(self, db_session):
        full  = search_products(db_session, query="salt rice bread", limit=50, offset=0)
        page2 = search_products(db_session, query="salt rice bread", limit=1,  offset=1)

        assert len(page2.results) == 1
        # The first result of the offset-1 page must equal the second result of the full page
        assert page2.results[0].product_id == full.results[1].product_id, (
            f"offset=1 should start at full.results[1]: "
            f"expected {full.results[1].product_name}, "
            f"got {page2.results[0].product_name}"
        )

    def test_sequential_pages_cover_all_results(self, db_session):
        """Sliding offset=0,1,2 across limit=1 windows must yield every match exactly once."""
        full = search_products(db_session, query="salt rice bread", limit=50, offset=0)
        full_ids = [item.product_id for item in full.results]

        paged_ids = []
        for i in range(full.total):
            page = search_products(
                db_session, query="salt rice bread", limit=1, offset=i,
            )
            assert len(page.results) == 1, f"Expected 1 result at offset={i}"
            paged_ids.append(page.results[0].product_id)

        assert paged_ids == full_ids, (
            f"Paginated traversal produced different order:\n"
            f"  full  : {full_ids}\n"
            f"  paged : {paged_ids}"
        )

    def test_offset_beyond_total_returns_empty(self, db_session):
        """An offset larger than total must produce an empty result list, not an error."""
        full   = search_products(db_session, query="salt", limit=10, offset=0)
        beyond = search_products(db_session, query="salt", limit=10, offset=full.total + 100)

        assert beyond.results == []
        # total must still reflect the full match count, not the page size
        assert beyond.total == full.total

    def test_limit_and_offset_echoed_in_response(self, db_session):
        """SearchResponse must echo back the exact limit and offset that were sent."""
        result = search_products(db_session, query="salt", limit=7, offset=2)
        assert result.limit  == 7
        assert result.offset == 2


class TestOrmRelationshipResolution:
    """category, subcategory, and vendor.shop_name must resolve without detachment errors."""

    def test_category_name_resolved(self, db_session):
        result = search_products(db_session, query="salt", limit=1, offset=0)

        assert len(result.results) >= 1
        item = result.results[0]
        assert item.category == "Groceries", (
            f"Expected category='Groceries', got {item.category!r}"
        )

    def test_subcategory_name_resolved(self, db_session):
        result = search_products(db_session, query="salt", limit=1, offset=0)

        item = result.results[0]
        assert item.subcategory == "Staples", (
            f"Expected subcategory='Staples', got {item.subcategory!r}"
        )

    def test_vendor_detail_populated(self, db_session):
        """vendor must not be None and must carry the correct shop coordinates."""
        result = search_products(db_session, query="salt", limit=1, offset=0)

        item = result.results[0]
        assert item.vendor is not None, "vendor should not be None after joinedload"
        assert item.vendor.shop_name == "Super Store", (
            f"Expected shop_name='Super Store', got {item.vendor.shop_name!r}"
        )
        assert item.vendor.shop_location_lat == pytest.approx(12.97), (
            f"Unexpected lat: {item.vendor.shop_location_lat}"
        )
        assert item.vendor.shop_location_lon == pytest.approx(77.59), (
            f"Unexpected lon: {item.vendor.shop_location_lon}"
        )

    def test_all_items_have_resolved_relationships(self, db_session):
        """Every item in a multi-result page must have non-empty category and subcategory."""
        result = search_products(
            db_session, query="salt rice bread", limit=50, offset=0,
        )
        assert len(result.results) >= 2, "Need at least 2 results for this assertion"

        for item in result.results:
            assert item.category,    f"Empty category on {item.product_name}"
            assert item.subcategory, f"Empty subcategory on {item.product_name}"
            assert item.vendor is not None, f"None vendor on {item.product_name}"
            assert item.vendor.vendor_id, f"Empty vendor_id on {item.product_name}"

    def test_query_is_echoed_in_response(self, db_session):
        """SearchResponse.query must echo back the stripped query string."""
        result = search_products(db_session, query="  salt  ", limit=5, offset=0)
        # search_products strips the query internally
        assert result.query == "salt", (
            f"Expected echoed query='salt', got {result.query!r}"
        )
