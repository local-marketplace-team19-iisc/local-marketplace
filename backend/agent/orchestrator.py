"""Orchestrator: the main turn loop.

For every incoming user message:
1. Load or create the session.
2. If a confirmation is pending, short-circuit: detect yes/no.
3. Otherwise: planner → validate tool calls → execute → loop (bounded).
4. Persist turn, return assistant message.

Hard invariants:
- LLM output is always validated against PlannerOutput (Pydantic).
- Tool args are always validated against each tool's input_model.
- Tools marked `requires_confirm` NEVER execute on the turn they were
  proposed; they are stored as session.pending_action and executed only
  after the next user turn classified as affirmative.
- max_tools_chain_depth bounds the inner loop.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from backend.agent.memory import SessionStore, build_store, new_session
from backend.agent.planner import Planner, build_llm_client
from backend.agent.schemas import (
    Channel,
    Message,
    PendingAction,
    Session,
    ToolCall,
    ToolResult,
    TokenUsage,
    Turn,
    TurnResponse,
)
from backend.agent.tools import REGISTRY
from backend.agent.tools.base import ToolContext
from backend.agent.tools.nlp_tools import is_affirmative, is_negative


class Orchestrator:
    def __init__(self, cfg, store: SessionStore | None = None) -> None:
        self.cfg = cfg
        self.store: SessionStore = store or build_store(cfg)
        self.planner = Planner(cfg, build_llm_client(cfg))

    # ----- public entry point --------------------------------------------

    async def handle_turn(
        self,
        *,
        session_id: str | None,
        user_id: str | None,
        channel: Channel,
        user_input: Message,
    ) -> TurnResponse:
        t0 = time.perf_counter()
        session = await self._get_or_create(session_id, user_id, channel)
        session.last_active_at = datetime.now(timezone.utc)
        if user_input.geo and not session.location:
            session.location = user_input.geo
        if user_input.language:
            session.language = user_input.language

        turn = Turn(turn_id=f"turn_{uuid.uuid4().hex[:8]}", user_msg=user_input)

        # --- Pending-confirmation short-circuit --------------------------
        if session.pending_action and is_affirmative(user_input.text):
            tool_result = await self._execute_confirmed(session)
            session.pending_action = None
            turn.tool_results = [tool_result]
            assistant_text = self._render_confirmed(tool_result)
            turn.assistant_msg = Message(text=assistant_text, language=session.language)
            await self._commit_turn(session, turn, t0)
            return self._build_response(session, turn, t0)

        # Explicit "no" while a pending action exists → cancel it.
        if session.pending_action and is_negative(user_input.text):
            session.pending_action = None
            turn.assistant_msg = Message(text="Okay, cancelled.", language=session.language)
            await self._commit_turn(session, turn, t0)
            return self._build_response(session, turn, t0)

        # --- Normal planner loop -----------------------------------------
        scratchpad: list[ToolResult] = []
        depth_cap = int(self.cfg.safety.max_tools_chain_depth)
        per_turn_cap = int(self.cfg.safety.max_tool_calls_per_turn)
        tool_calls_used = 0
        final_text = ""
        total_usage = TokenUsage()

        for _step in range(depth_cap):
            for_args = True  # the planner's primary job is to emit tool args
            planner_out, usage = await self.planner.plan(
                session, user_input.text, scratchpad, for_tool_args=for_args,
            )
            total_usage.prompt += usage.get("prompt_tokens", 0)
            total_usage.completion += usage.get("completion_tokens", 0)
            turn.tool_calls.extend(planner_out.tool_calls)

            if not planner_out.tool_calls:
                final_text = planner_out.assistant
                break

            # Execute proposed tool calls, honouring per-turn cap.
            for call in planner_out.tool_calls:
                if tool_calls_used >= per_turn_cap:
                    break
                tool_calls_used += 1
                result = await self._dispatch(session, call)
                scratchpad.append(result)
                turn.tool_results.append(result)

                # If the tool requires confirmation, the planner shouldn't
                # have actually run it — `_dispatch` returns a `staged`
                # result and registers a pending_action instead.

            # If the planner already produced an assistant message alongside
            # tool calls (e.g. a preview), use it and stop.
            if planner_out.assistant:
                final_text = planner_out.assistant
                break

        if not final_text:
            final_text = "Sorry, I couldn't complete that. Could you try again?"

        turn.assistant_msg = Message(text=final_text, language=session.language)
        turn.tokens = total_usage
        await self._commit_turn(session, turn, t0)
        return self._build_response(session, turn, t0)

    # ----- helpers --------------------------------------------------------

    async def _get_or_create(
        self, session_id: str | None, user_id: str | None, channel: Channel,
    ) -> Session:
        if session_id:
            existing = await self.store.get(session_id)
            if existing:
                return existing
        return new_session(user_id=user_id, channel=channel)

    async def _dispatch(self, session: Session, call: ToolCall) -> ToolResult:
        tool = REGISTRY.get(call.name)
        if tool is None:
            return ToolResult(name=call.name, ok=False, error="unknown_tool")
        if not tool.is_allowed_for(session.role):
            return ToolResult(name=call.name, ok=False,
                              error=f"forbidden_for_role:{session.role}")

        # Confirmation gating: stage the call instead of running it.
        if tool.requires_confirm:
            session.pending_action = PendingAction(
                tool_name=call.name, args=call.args,
                created_at=datetime.now(timezone.utc),
            )
            return ToolResult(
                name=call.name, ok=True,
                data={"staged": True, "args": call.args},
            )

        ctx = ToolContext(
            session_id=session.session_id,
            user_id=session.user_id,
            role=session.role,
            config=self.cfg,
        )
        return await tool.run(call.args, ctx)

    async def _execute_confirmed(self, session: Session) -> ToolResult:
        assert session.pending_action is not None
        pa = session.pending_action
        tool = REGISTRY.get(pa.tool_name)
        if tool is None:
            return ToolResult(name=pa.tool_name, ok=False,
                              error="unknown_tool_at_confirm_time")
        if not tool.is_allowed_for(session.role):
            return ToolResult(name=pa.tool_name, ok=False,
                              error="role_changed_since_staging")
        ctx = ToolContext(
            session_id=session.session_id, user_id=session.user_id,
            role=session.role, config=self.cfg,
        )
        return await tool.run(pa.args, ctx)

    def _render_confirmed(self, result: ToolResult) -> str:
        """Render the user-facing message after a confirmed action ran.

        Per-tool rendering. The set is small enough in baseline that a flat
        if-elif is clearer than a renderer registry. Anything not listed
        falls back to a generic acknowledgement.
        """
        if not result.ok:
            return f"Couldn't complete that: {result.error or 'unknown error'}."

        data = result.data or {}
        if result.name == "add_product":
            pid = data.get("product_id", "?")
            name = data.get("name", "the product")
            price = data.get("price")
            unit = data.get("unit", "")
            qty = data.get("quantity", "")
            return (
                f"Listed ✅  {name} ({qty} {unit}) @ ₹{price} — "
                f"product id: {pid}"
            )
        return "Done ✅"

    async def _commit_turn(self, session: Session, turn: Turn, t0: float) -> None:
        turn.latency_ms = int((time.perf_counter() - t0) * 1000)
        session.turns.append(turn)
        # Roll the window to keep memory + prompt size bounded.
        cap = int(self.cfg.session.max_turns_in_context) * 2
        if len(session.turns) > cap:
            session.turns = session.turns[-cap:]
        await self.store.save(session)

    def _build_response(self, session: Session, turn: Turn, t0: float) -> TurnResponse:
        return TurnResponse(
            session_id=session.session_id,
            turn_id=turn.turn_id,
            assistant=turn.assistant_msg.text if turn.assistant_msg else "",
            pending_action=session.pending_action,
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
