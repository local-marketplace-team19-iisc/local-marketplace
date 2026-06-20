"""Tool registry — imports the side-effect of registration.

Baseline scope (this round): vendor extract+add+catalog, customer
search+get_store, and the orchestrator-internal `is_affirmative` helper.

Shared tools (geocode, set_user_location, escalate, ...) are deferred and
deliberately NOT imported here. They live in `shared_tools.py` and are
available to re-enable when promoted into baseline.
"""

from .base import REGISTRY, Tool, tool  # noqa: F401
from . import vendor_tools  # noqa: F401
from . import customer_tools  # noqa: F401
from . import nlp_tools  # noqa: F401
