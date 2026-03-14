from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict

from models.action_schema import Action, ActionType
from models.policy_schema import Policy


class OpenClawExecutor:
    """Executes policy-approved actions against the local filesystem."""

    def __init__(self, policy: Policy) -> None:
        self.policy = policy

    def execute(self, action: Action) -> Dict[str, str]:
        if action.type == ActionType.DELETE:
            return self._delete(Path(action.path or ""))

        if action.type == ActionType.CLEAN_DIRECTORY:
            return self._clean_directory(Path(action.path or ""))

        if action.type == ActionType.RUN_COMMAND:
            return self._run_command(action.command or [], Path(action.target or self.policy.project_root))

        if action.type == ActionType.MOVE:
            return self._move(Path(action.source or ""), Path(action.destination or ""))

        if action.type == ActionType.GENERATE_COMMIT_MESSAGE:
            return self._generate_commit_message(Path(action.target or self.policy.project_root))

        return {"status": "error", "detail": f"Unsupported action {action.type.value}"}

    def _delete(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {"status": "ok", "detail": f"Path not found: {path} (noop)"}

        if path.is_dir():
            shutil.rmtree(path)
            return {"status": "ok", "detail": f"Deleted directory: {path}"}

        path.unlink()
        return {"status": "ok", "detail": f"Deleted file: {path}"}

    def _clean_directory(self, path: Path) -> Dict[str, str]:
        if not path.exists() or not path.is_dir():
            return {"status": "ok", "detail": f"Directory not found: {path} (noop)"}

        removed = 0
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed += 1

        return {"status": "ok", "detail": f"Cleaned directory {path}; removed {removed} entries"}

    def _run_command(self, command: list[str], target: Path) -> Dict[str, str]:
        if not command:
            return {"status": "error", "detail": "Empty command"}

        normalized = list(command)
        if normalized[0].lower() == "python":
            # Keep command policy simple while guaranteeing interpreter consistency.
            normalized[0] = sys.executable

        # shell=False prevents command injection through shell interpretation.
        completed = subprocess.run(
            normalized,
            cwd=target,
            shell=False,
            capture_output=True,
            text=True,
            timeout=self.policy.max_command_runtime_seconds,
            check=False,
        )

        result = {
            "status": "ok" if completed.returncode == 0 else "error",
            "detail": f"Command exited with {completed.returncode}",
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
        return result

    def _move(self, source: Path, destination: Path) -> Dict[str, str]:
        if not source.exists():
            return {"status": "ok", "detail": f"Source not found: {source} (noop)"}

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return {"status": "ok", "detail": f"Moved {source} -> {destination}"}

    def _generate_commit_message(self, target: Path) -> Dict[str, str]:
        command = ["git", "status", "--short"]
        completed = subprocess.run(
            command,
            cwd=target,
            shell=False,
            capture_output=True,
            text=True,
            timeout=self.policy.max_command_runtime_seconds,
            check=False,
        )

        if completed.returncode != 0:
            return {
                "status": "error",
                "detail": "Failed to inspect git status",
                "stderr": completed.stderr.strip(),
            }

        changes = [line for line in completed.stdout.splitlines() if line.strip()]
        summary = f"chore: apply autonomous maintenance ({len(changes)} changed paths)"
        return {
            "status": "ok",
            "detail": "Generated commit message",
            "message": summary,
            "changes": json.dumps(changes),
        }
