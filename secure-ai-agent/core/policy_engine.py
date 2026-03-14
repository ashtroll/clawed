from __future__ import annotations

from pathlib import Path
from typing import Iterable

from models.action_schema import Action, ActionType, PolicyDecision
from models.policy_schema import Policy


class PolicyEngine:
    """Deterministic runtime policy enforcement for every action."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.policy.validate()
        self.project_root = Path(policy.project_root).resolve()
        self.allowed_directories = [Path(d).resolve() for d in policy.allowed_directories]
        self.protected_directories = [Path(d).resolve() for d in policy.protected_directories]

    def evaluate(self, action: Action) -> PolicyDecision:
        # Route all checks by action type for transparent, deterministic behavior.
        if action.type in {ActionType.DELETE, ActionType.CLEAN_DIRECTORY}:
            if not action.path:
                return PolicyDecision(False, "Missing path for delete/clean action")
            return self._validate_path_operation(Path(action.path))

        if action.type == ActionType.MOVE:
            if not action.source or not action.destination:
                return PolicyDecision(False, "Missing source/destination for move action")
            source_result = self._validate_path_operation(Path(action.source))
            if not source_result.allowed:
                return source_result
            destination_result = self._validate_path_operation(Path(action.destination), must_exist=False)
            if not destination_result.allowed:
                return destination_result
            return PolicyDecision(True, "Move action allowed")

        if action.type == ActionType.RUN_COMMAND:
            return self._validate_command(action.command or [], action.target)

        if action.type == ActionType.GENERATE_COMMIT_MESSAGE:
            target = Path(action.target or self.project_root)
            return self._validate_path_operation(target, must_exist=True)

        return PolicyDecision(False, f"Unsupported action type: {action.type.value}")

    def _validate_path_operation(self, path: Path, must_exist: bool = False) -> PolicyDecision:
        resolved = path.resolve()

        if not self._is_within(resolved, self.project_root):
            return PolicyDecision(False, "Path escapes project root")

        if not any(self._is_within(resolved, d) for d in self.allowed_directories):
            return PolicyDecision(False, "Path outside allowed directories")

        if any(self._is_within(resolved, p) for p in self.protected_directories):
            return PolicyDecision(False, "Protected directory access")

        if any(token in resolved.name.lower() for token in self.policy.protected_files):
            return PolicyDecision(False, "Protected file access")

        if must_exist and not resolved.exists():
            return PolicyDecision(False, "Target does not exist")

        return PolicyDecision(True, "Path operation allowed")

    def _validate_command(self, command: Iterable[str], target: str | None) -> PolicyDecision:
        command = list(command)
        if not command:
            return PolicyDecision(False, "Empty command")

        executable = command[0].lower()

        # Block known risky commands before allow-list check.
        if executable in {c.lower() for c in self.policy.blocked_commands}:
            return PolicyDecision(False, "Command explicitly blocked")

        if executable not in {c.lower() for c in self.policy.allowed_commands}:
            return PolicyDecision(False, "Command not in allow-list")

        joined = " ".join(command)
        if any(substr in joined for substr in self.policy.blocked_substrings):
            return PolicyDecision(False, "Command contains blocked shell metacharacters")

        if target is not None:
            target_result = self._validate_path_operation(Path(target), must_exist=True)
            if not target_result.allowed:
                return target_result

        return PolicyDecision(True, "Command allowed")

    @staticmethod
    def _is_within(candidate: Path, parent: Path) -> bool:
        try:
            candidate.relative_to(parent)
            return True
        except ValueError:
            return False
