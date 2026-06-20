"""End-to-end orchestrator tests with a deterministic fake LLM client.

What we verify:
1. Confirmation gating — `add_product` does NOT execute on the turn it's
   proposed; it stages a pending_action and runs only after the user replies
   "yes" on the next turn.
2. Explicit "no" cancels the pending_action without writing.
3. Role gating — a customer's planner attempting to call a vendor tool is
   rejected by the registry (`forbidden_for_role:customer`).
4. Search round-trip — vendor seeds products, customer's planner proposes
   `search_products`, the orchestrator executes it and surfaces matches.
"""
from __future__ import annotations

import pytest

from backend.agent.memory import InMemoryStore, new_session
from backend.agent.orchestrator import Orchestrator
from backend.agent.planner import Planner
from backend.agent.schemas import Message, PlannerOutput, Role, ToolCall
from backend.agent.tools import _store
from backend.agent.utils.config import load_config


# --------------------------------------------------------------------------- #
# Fake LLM client: returns a scripted sequence of PlannerOutput payloads.
# --------------------------------------------------------------------------- #


class ScriptedLLMClient:
    """Returns the next PlannerOutput from a list, then sticks on the last."""

    def __init__(self, script: list[PlannerOutput]) -> None:
        self._script = list(script)
        self._idx = 0

    async def complete(self, **_kw) -> tuple[str, dict[str, int]]:
        if not self._script:
            payload = PlannerOutput(thought="", tool_calls=[], assistant="(empty script)")
        elif self._idx < len(self._script):
            payload = self._script[self._idx]
            self._idx += 1
        else:
            payload = self._script[-1]
        return payload.model_dump_json(), {"prompt_tokens": 0, "completion_tokens": 0}


@pytest.fixture(autouse=True)
def _reset_store():
    _store.reset_store()
    yield
    _store.reset_store()


@pytest.fixture
def cfg():
    # Resolve config relative to the agent package so tests work from any CWD.
    from pathlib import Path
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "agent.yaml"
    return load_config(str(cfg_path))


def _make_orch(cfg, script: list[PlannerOutput]) -> Orchestrator:
    # Force the in-memory session store so tests never need Redis, even if
    # the resolved config has `session.store: redis`. We also swap in the
    # scripted LLM client so no real network calls happen.
    orch = Orchestrator(cfg, store=InMemoryStore(ttl_seconds=300))
    orch.planner = Planner(cfg, ScriptedLLMClient(script))
    return orch


async def _seed_session(orch: Orchestrator, *, user_id: str, role: Role) -> str:
    sess = new_session(user_id=user_id, channel="web", role=role)
    await orch.store.save(sess)
    return sess.session_id


# --------------------------------------------------------------------------- #
# 1. Confirmation gating
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_add_product_requires_confirmation_then_executes(cfg):
    script = [
        PlannerOutput(
            thought="extracted draft",
            tool_calls=[ToolCall(
                name="add_product",
                args={
                    "name": "Sona Masuri Rice", "category": "Grocery",
                    "price": 58.0, "quantity": 10, "unit": "kg",
                    "confidence": 0.9,
                },
            )],
            assistant="Add Sona Masuri 10 kg @ ₹58? Reply 'yes' to confirm.",
        ),
        PlannerOutput(thought="", tool_calls=[], assistant="(unused)"),
    ]
    orch = _make_orch(cfg, script)
    sid = await _seed_session(orch, user_id="v_demo", role="vendor")

    r1 = await orch.handle_turn(
        session_id=sid, user_id="v_demo", channel="web",
        user_input=Message(text="Add 10 kg Sona Masuri rice ₹58/kg"),
    )
    assert r1.pending_action is not None
    assert r1.pending_action.tool_name == "add_product"
    assert _store.snapshot()["products"] == 0, "no DB write on the proposal turn"

    r2 = await orch.handle_turn(
        session_id=sid, user_id="v_demo", channel="web",
        user_input=Message(text="yes"),
    )
    assert r2.pending_action is None
    assert _store.snapshot()["products"] == 1
    assert "Listed" in r2.assistant or "p_1" in r2.assistant


@pytest.mark.asyncio
async def test_explicit_no_cancels_pending_action(cfg):
    script = [
        PlannerOutput(
            thought="",
            tool_calls=[ToolCall(
                name="add_product",
                args={
                    "name": "Test", "category": "Grocery",
                    "price": 1.0, "quantity": 1, "unit": "kg",
                    "confidence": 0.9,
                },
            )],
            assistant="Confirm?",
        ),
        PlannerOutput(thought="", tool_calls=[], assistant="(unused)"),
    ]
    orch = _make_orch(cfg, script)
    sid = await _seed_session(orch, user_id="v_demo", role="vendor")

    r1 = await orch.handle_turn(
        session_id=sid, user_id="v_demo", channel="web",
        user_input=Message(text="Add 1 kg test ₹1"),
    )
    assert r1.pending_action is not None

    r2 = await orch.handle_turn(
        session_id=sid, user_id="v_demo", channel="web",
        user_input=Message(text="no"),
    )
    assert r2.pending_action is None
    assert _store.snapshot()["products"] == 0
    assert "cancel" in r2.assistant.lower()


# --------------------------------------------------------------------------- #
# 2. Role gating
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_customer_cannot_invoke_vendor_tool(cfg):
    script = [
        PlannerOutput(
            thought="",
            tool_calls=[ToolCall(
                name="add_product",
                args={
                    "name": "Foo", "category": "Bar",
                    "price": 1.0, "quantity": 1, "unit": "kg",
                    "confidence": 0.9,
                },
            )],
            assistant="",
        ),
        PlannerOutput(thought="", tool_calls=[],
                      assistant="Sorry, I can't add products as a customer."),
    ]
    orch = _make_orch(cfg, script)
    sid = await _seed_session(orch, user_id="c_demo", role="customer")

    r = await orch.handle_turn(
        session_id=sid, user_id="c_demo", channel="web",
        user_input=Message(text="add a product"),
    )

    sess = await orch.store.get(r.session_id)
    assert sess is not None
    last_turn = sess.turns[-1]
    bad = [tr for tr in last_turn.tool_results if tr.name == "add_product"]
    assert bad and bad[0].ok is False
    assert "forbidden_for_role:customer" in (bad[0].error or "")
    assert _store.snapshot()["products"] == 0


# --------------------------------------------------------------------------- #
# 3. Customer search round-trip
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_customer_search_returns_seeded_products(cfg):
    from backend.agent.tools import REGISTRY
    from backend.agent.tools.base import ToolContext

    vctx = ToolContext(
        session_id="seed", user_id="v_a", role="vendor", config=cfg,
    )
    await REGISTRY["add_product"].run(
        {
            "name": "Sona Masuri Rice 10kg", "category": "Grocery",
            "price": 580, "quantity": 10, "unit": "kg", "confidence": 0.9,
        },
        vctx,
    )
    await REGISTRY["add_product"].run(
        {
            "name": "IR-20 Rice 10kg", "category": "Grocery",
            "price": 540, "quantity": 10, "unit": "kg", "confidence": 0.9,
        },
        vctx,
    )

    script = [
        PlannerOutput(
            thought="",
            tool_calls=[ToolCall(
                name="search_products",
                args={"text": "rice 10kg", "radius_km": 25.0},
            )],
            assistant="",
        ),
        PlannerOutput(
            thought="rendering cards",
            tool_calls=[],
            assistant="Top matches: Sona Masuri Rice 10kg, IR-20 Rice 10kg",
        ),
    ]
    orch = _make_orch(cfg, script)
    sid = await _seed_session(orch, user_id="c_demo", role="customer")

    r = await orch.handle_turn(
        session_id=sid, user_id="c_demo", channel="web",
        user_input=Message(text="rice 10kg near me"),
    )

    # The orchestrator must have run search_products and stored the result.
    sess = await orch.store.get(r.session_id)
    assert sess is not None
    last_turn = sess.turns[-1]
    search_results = [tr for tr in last_turn.tool_results if tr.name == "search_products"]
    assert search_results and search_results[0].ok
    names = [r["name"] for r in search_results[0].data["results"]]
    assert "Sona Masuri Rice 10kg" in names
    assert "Sona Masuri" in r.assistant
