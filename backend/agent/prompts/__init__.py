"""System prompts (loaded from text files in this directory)."""
from pathlib import Path

_HERE = Path(__file__).parent


def load(name: str) -> str:
    return (_HERE / name).read_text(encoding="utf-8")
