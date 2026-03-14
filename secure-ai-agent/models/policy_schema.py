from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Policy:
    """ArmorClaw-style deterministic security policy."""

    project_root: str
    allowed_directories: List[str] = field(default_factory=list)
    protected_files: List[str] = field(default_factory=list)
    protected_directories: List[str] = field(default_factory=list)
    allowed_commands: List[str] = field(default_factory=list)
    blocked_commands: List[str] = field(default_factory=list)
    blocked_substrings: List[str] = field(default_factory=lambda: ["&&", ";", "|", "`", "$("])
    max_command_runtime_seconds: int = 20

    def validate(self) -> None:
        if not self.project_root.strip():
            raise ValueError("project_root is required")
        if not self.allowed_directories:
            raise ValueError("allowed_directories cannot be empty")
