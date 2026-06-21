"""Copy the repo's authoritative SKILL.md to the user-global skills directories.

Run after editing ``skills/computer-use/SKILL.md`` so frameworks that load from
the user-global location pick up the change.

Why copy (not symlink): agent frameworks modify files with delete-then-write,
which replaces a symlink with a plain file and breaks the link. A re-runnable
copy is the reliable mechanism.

Targets:
  - ~/.agents/skills/computer-use/SKILL.md   (always — primary deployment target)
  - ~/.claude/skills/computer-use/SKILL.md   (updated only if already installed
    there; not created, so we never auto-enable the skill in Claude Code)
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_SOURCE = Path(__file__).resolve().parent.parent / "skills" / "computer-use" / "SKILL.md"


def _targets() -> list[Path]:
    home = Path.home()
    targets = [home / ".agents" / "skills" / "computer-use" / "SKILL.md"]
    # Update an existing Claude Code install, but do not create one — that would
    # silently enable the skill globally in Claude Code without the user opting in.
    claude_skill = home / ".claude" / "skills" / "computer-use" / "SKILL.md"
    if claude_skill.exists():
        targets.append(claude_skill)
    return targets


def main() -> int:
    if not _SOURCE.is_file():
        print(f"source SKILL not found: {_SOURCE}", file=sys.stderr)
        return 1
    for dest in _targets():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_SOURCE, dest)
        print(f"synced -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
