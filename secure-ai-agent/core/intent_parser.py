from __future__ import annotations

from pathlib import Path

from core.reasoning import ReasoningLayer
from models.intent_schema import StructuredIntent


class IntentParser:
    """Transforms natural language prompts into a strict intent schema."""

    def __init__(self, reasoning_layer: ReasoningLayer) -> None:
        self.reasoning_layer = reasoning_layer

    def parse(self, user_prompt: str, project_root: Path) -> StructuredIntent:
        reasoning = self.reasoning_layer.infer(user_prompt=user_prompt, project_root=project_root)

        allowed_actions = self._infer_allowed_actions(user_prompt)
        intent = StructuredIntent(
            intent=reasoning.intent_name,
            target_directory=reasoning.target_directory,
            allowed_actions=allowed_actions,
            raw_prompt=user_prompt,
            reasoning_summary=reasoning.reasoning_summary,
        )
        intent.validate()
        return intent

    @staticmethod
    def _infer_allowed_actions(user_prompt: str) -> list[str]:
        text = user_prompt.lower()
        actions: list[str] = []

        if any(token in text for token in ["clean", "cleanup", "delete", "remove"]):
            actions.append("delete_temp_files")
        if any(token in text for token in ["format", "black", "isort", "prettier"]):
            actions.append("format_code")
        if any(token in text for token in ["lint", "eslint", "ruff", "flake8"]):
            actions.append("run_linter")
        if any(token in text for token in ["reorganize", "reorganise", "move"]):
            actions.append("reorganize_folders")
        if "commit" in text and "message" in text:
            actions.append("create_commit_message")

        if not actions:
            actions.append("inspect_project")

        return actions
