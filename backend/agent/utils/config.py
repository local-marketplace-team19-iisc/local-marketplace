"""YAML config loader with dotted-key CLI overrides.

Usage:
    cfg = load_config("config/agent.yaml", overrides=["llm.planner.model=gpt-4o"])
    print(cfg.llm.planner.model)
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import yaml


def _to_namespace(obj: Any) -> Any:
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(v) for v in obj]
    return obj


def _coerce(raw: str) -> Any:
    """Coerce CLI string into int/float/bool/None/str."""
    low = raw.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", "~"):
        return None
    try:
        if "." in raw or "e" in low:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _apply_override(tree: dict, dotted: str) -> None:
    if "=" not in dotted:
        raise ValueError(f"override must be key=value, got: {dotted!r}")
    key, raw = dotted.split("=", 1)
    parts = key.strip().split(".")
    node = tree
    for p in parts[:-1]:
        if p not in node or not isinstance(node[p], dict):
            node[p] = {}
        node = node[p]
    node[parts[-1]] = _coerce(raw.strip())


def load_config(
    path: str | Path = "config/agent.yaml",
    overrides: Iterable[str] | None = None,
) -> SimpleNamespace:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        tree = yaml.safe_load(f) or {}

    for ov in overrides or []:
        _apply_override(tree, ov)

    return _to_namespace(tree)
