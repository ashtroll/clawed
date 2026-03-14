from __future__ import annotations

from pathlib import Path
from typing import List

from models.action_schema import Action, ActionType
from models.intent_schema import StructuredIntent


class ActionPlanner:
    """Converts structured intent into atomic action objects."""

    def build_plan(self, intent: StructuredIntent) -> List[Action]:
        root = Path(intent.target_directory)
        actions: List[Action] = []

        if "delete_temp_files" in intent.allowed_actions:
            actions.extend(
                [
                    Action(type=ActionType.DELETE, path=str(root / "tmp")),
                    Action(type=ActionType.DELETE, path=str(root / ".env")),
                ]
            )

        if "format_code" in intent.allowed_actions:
            actions.append(
                Action(
                    type=ActionType.RUN_COMMAND,
                    command=["python", "-m", "black", "."],
                    target=str(root),
                )
            )

        if "run_linter" in intent.allowed_actions:
            actions.append(
                Action(
                    type=ActionType.RUN_COMMAND,
                    command=["python", "-m", "ruff", "check", "."],
                    target=str(root),
                )
            )

        if "reorganize_folders" in intent.allowed_actions:
            actions.append(
                Action(
                    type=ActionType.MOVE,
                    source=str(root / "old_docs"),
                    destination=str(root / "docs" / "archive"),
                )
            )

        if "create_commit_message" in intent.allowed_actions:
            actions.append(
                Action(type=ActionType.GENERATE_COMMIT_MESSAGE, target=str(root))
            )

        if not actions:
            actions.append(Action(type=ActionType.CLEAN_DIRECTORY, path=str(root / "tmp")))

        return actions
