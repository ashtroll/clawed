from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class DelegationScope:
    """
    Defines the bounded authority a parent agent grants to a sub-agent.

    The scope must be a strict subset of the parent's policy—validation
    raises ValueError if any granted permission exceeds the parent's own
    authority.
    """

    allowed_action_types: List[str]   # subset of ActionType values, e.g. ["run_command"]
    allowed_commands: List[str] = field(default_factory=list)
    allowed_directories: List[str] = field(default_factory=list)
    delegated_by: str = "parent_agent"
    reason: str = ""

    def validate_against_parent(
        self,
        parent_allowed_commands: List[str],
        parent_allowed_directories: List[str],
    ) -> None:
        """
        Enforce that this delegation scope does not exceed the parent's policy.

        Raises ValueError with a descriptive message on any violation so the
        delegation itself is rejected before a single action is attempted.
        """
        parent_cmds = {c.lower() for c in parent_allowed_commands}
        for cmd in self.allowed_commands:
            if cmd.lower() not in parent_cmds:
                raise ValueError(
                    f"Delegation scope exceeds parent authority: "
                    f"command '{cmd}' is not in the parent's allowed_commands"
                )

        parent_dirs = [Path(d).resolve() for d in parent_allowed_directories]
        for d in self.allowed_directories:
            resolved = Path(d).resolve()
            if not any(_is_within(resolved, p) for p in parent_dirs):
                raise ValueError(
                    f"Delegation scope exceeds parent authority: "
                    f"directory '{d}' is outside the parent's allowed_directories"
                )


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
        return True
    except ValueError:
        return False
