"""Tool base class and decorator-based registry.

A Tool is a typed Python callable that the planner can invoke.
Every tool declares:
- name              : snake_case identifier
- roles             : which session roles may call it
- side_effect       : "read" | "write" | "external"
- requires_confirm  : if True, orchestrator gates execution behind a
                      `pending_action` + affirmative user reply
- input_model       : Pydantic model for args (validated before call)
- output_model      : Pydantic model for result (validated after call)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, ValidationError

from backend.agent.schemas import Role, ToolResult


SideEffect = Literal["read", "write", "external"]


@dataclass
class Tool:
    name: str
    fn: Callable[..., Awaitable[BaseModel]]
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    roles: frozenset[Role]
    side_effect: SideEffect
    requires_confirm: bool = False
    description: str = ""

    def is_allowed_for(self, role: Role) -> bool:
        return role in self.roles

    async def run(self, raw_args: dict[str, Any], ctx: "ToolContext") -> ToolResult:
        t0 = time.perf_counter()
        try:
            args = self.input_model(**raw_args)
        except ValidationError as e:
            return ToolResult(
                name=self.name, ok=False,
                error=f"input_validation_failed: {e.errors()[:3]}",
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        try:
            result = await self.fn(args, ctx)
            # round-trip through the output model for safety
            validated = self.output_model.model_validate(result.model_dump())
            return ToolResult(
                name=self.name, ok=True,
                data=validated.model_dump(mode="json"),
                latency_ms=int((time.perf_counter() - t0) * 1000),
            )
        except asyncio.TimeoutError:
            return ToolResult(name=self.name, ok=False, error="timeout",
                              latency_ms=int((time.perf_counter() - t0) * 1000))
        except Exception as e:  # noqa: BLE001
            return ToolResult(name=self.name, ok=False, error=f"{type(e).__name__}: {e}",
                              latency_ms=int((time.perf_counter() - t0) * 1000))


@dataclass
class ToolContext:
    """What every tool sees about the current invocation."""
    session_id: str
    user_id: str | None
    role: Role
    config: Any  # SimpleNamespace from utils.config
    # Inject backends here in production: db, cache, vector_store, search, ...


REGISTRY: dict[str, Tool] = {}


def tool(
    *,
    name: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    roles: list[Role],
    side_effect: SideEffect,
    requires_confirm: bool = False,
    description: str = "",
) -> Callable[[Callable[..., Awaitable[BaseModel]]], Tool]:
    """Decorator that registers a tool by name."""
    def deco(fn: Callable[..., Awaitable[BaseModel]]) -> Tool:
        if name in REGISTRY:
            raise RuntimeError(f"duplicate tool registration: {name!r}")
        t = Tool(
            name=name, fn=fn,
            input_model=input_model, output_model=output_model,
            roles=frozenset(roles), side_effect=side_effect,
            requires_confirm=requires_confirm, description=description,
        )
        REGISTRY[name] = t
        return t
    return deco


def tools_for_role(role: Role) -> list[Tool]:
    return [t for t in REGISTRY.values() if t.is_allowed_for(role)]


def tool_schemas_for_prompt(role: Role) -> list[dict[str, Any]]:
    """Compact JSON-Schema-ish description of each tool for the system prompt."""
    schemas: list[dict[str, Any]] = []
    for t in tools_for_role(role):
        schemas.append({
            "name": t.name,
            "description": t.description or t.fn.__doc__ or "",
            "side_effect": t.side_effect,
            "requires_confirm": t.requires_confirm,
            "args_schema": t.input_model.model_json_schema(),
        })
    return schemas
