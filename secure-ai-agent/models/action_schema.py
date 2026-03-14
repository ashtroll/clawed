from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ActionType(str, Enum):
    DELETE = "delete"
    CLEAN_DIRECTORY = "clean_directory"
    RUN_COMMAND = "run_command"
    MOVE = "move"
    GENERATE_COMMIT_MESSAGE = "generate_commit_message"


@dataclass(frozen=True)
class Action:
    """Atomic action planned by the planner and consumed by the executor."""

    type: ActionType
    path: Optional[str] = None
    source: Optional[str] = None
    destination: Optional[str] = None
    command: Optional[List[str]] = None
    target: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "type": self.type.value,
            "path": self.path,
            "source": self.source,
            "destination": self.destination,
            "command": self.command,
            "target": self.target,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
