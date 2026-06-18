#!/usr/bin/env python3
"""Switch the active SDD feature, auto-committing the current one first.

Flow (Constitution P3 audit trail · P7 .active_feature context binding):
  1. Refuse if the target feature folder does not exist under specs/ (typo guard).
  2. Auto-save the CURRENT feature: `git add` its specs/<current>/ slice and, if
     anything changed, create a new version (an auto commit) — git is the versioning.
  3. Point .active_feature at the target (the pointer itself is gitignored — P7).

Scope is deliberately narrow: only the current feature's folder is staged, so a
switch never sweeps up unrelated working-tree changes.

Usage:  python3 .claude/skills/switch/switch_feature.py <NNN-slug>
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

TRAILER = "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"


def find_repo_root() -> Path:
    for d in (Path.cwd(), *Path.cwd().parents):
        if (d / "specs" / "constitution.md").is_file():
            return d
    sys.exit("ERROR: not inside the repo — specs/constitution.md not found above CWD.")


def git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=check
    )


def feature_dirs(specs: Path) -> list[str]:
    return sorted(p.name for p in specs.iterdir() if p.is_dir())


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit("Usage: switch_feature.py <NNN-slug>   e.g. 002-vendor-onboarding")
    target = sys.argv[1].strip()

    root = find_repo_root()
    specs = root / "specs"

    # 1. Typo / existence guard — stop hard if the target feature is unknown.
    if not (specs / target).is_dir():
        avail = "\n  - ".join(feature_dirs(specs)) or "(none)"
        sys.exit(
            f"ERROR: no such feature '{target}' exists under specs/.\n"
            f"Available features:\n  - {avail}\n"
            "Switch aborted — check for a typo or scaffold it first with /spec-create."
        )

    if not (root / ".git").exists():
        sys.exit("ERROR: not a git repository — cannot version/commit the switch.")

    active = root / ".active_feature"
    current = active.read_text().strip() if active.exists() else ""

    committed = False
    note = ""
    if current and (specs / current).is_dir():
        # 2. Auto-save the current feature's slice as a new version.
        git(root, "add", "-A", "--", f"specs/{current}")
        has_changes = git(root, "diff", "--cached", "--quiet", check=False).returncode != 0
        if has_changes:
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            msg = (
                f"chore(specs/{current}): auto-checkpoint before switch -> {target}\n\n"
                f"Automated version saved by /switch at {stamp}.\n\n{TRAILER}"
            )
            git(root, "commit", "-m", msg)
            committed = True
        else:
            note = f"nothing new to commit in specs/{current} (already up to date)"
    elif current and not (specs / current).is_dir():
        note = f"current .active_feature -> '{current}' has no specs/ folder; skipped save"
    else:
        note = "no current active feature; nothing to save"

    # 3. Update the pointer.
    same = current == target
    active.write_text(target + "\n")

    print(f"From    : {current or '(none)'}")
    print(f"To      : {target}" + ("  (already active)" if same else ""))
    if committed:
        head = git(root, "rev-parse", "--short", "HEAD").stdout.strip()
        print(f"Saved   : committed specs/{current} as new version ({head})")
    if note:
        print(f"Note    : {note}")
    print(f".active_feature -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
