from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class StructuredIntent:
    """Structured intent emitted by the intent parsing layer."""

    intent: str
    target_directory: str
    allowed_actions: List[str] = field(default_factory=list)
    raw_prompt: str = ""
    reasoning_summary: str = ""

    def validate(self) -> None:
        if not self.intent.strip():
            raise ValueError("Intent must be non-empty")
        if not self.target_directory.strip():
            raise ValueError("Target directory must be non-empty")
