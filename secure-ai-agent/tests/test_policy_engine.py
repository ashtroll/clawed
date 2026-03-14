from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.policy_engine import PolicyEngine
from models.action_schema import Action, ActionType
from models.policy_schema import Policy


class PolicyEngineSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        self.root.mkdir(parents=True, exist_ok=True)

        (self.root / "tmp").mkdir(parents=True, exist_ok=True)
        (self.root / "config").mkdir(parents=True, exist_ok=True)
        (self.root / "database").mkdir(parents=True, exist_ok=True)
        (self.root / ".env").write_text("API_KEY=secret\n", encoding="utf-8")

        policy = Policy(
            project_root=str(self.root),
            allowed_directories=[str(self.root)],
            protected_files=[".env", "secret", "credentials", "keys"],
            protected_directories=[str(self.root / "config"), str(self.root / "database")],
            allowed_commands=["python", "black", "ruff", "git"],
            blocked_commands=["sudo", "chmod", "curl", "wget", "powershell", "cmd"],
        )
        self.engine = PolicyEngine(policy)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_allows_delete_inside_project(self) -> None:
        action = Action(type=ActionType.DELETE, path=str(self.root / "tmp"))
        decision = self.engine.evaluate(action)
        self.assertTrue(decision.allowed)

    def test_blocks_protected_file_delete(self) -> None:
        action = Action(type=ActionType.DELETE, path=str(self.root / ".env"))
        decision = self.engine.evaluate(action)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Protected file access")

    def test_blocks_directory_traversal_variant(self) -> None:
        outside = self.root.parent / "outside.txt"
        traversal = self.root / "tmp" / ".." / ".." / outside.name
        action = Action(type=ActionType.DELETE, path=str(traversal))
        decision = self.engine.evaluate(action)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Path escapes project root")

    def test_blocks_access_to_protected_directory(self) -> None:
        action = Action(type=ActionType.DELETE, path=str(self.root / "config" / "settings.yml"))
        decision = self.engine.evaluate(action)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Protected directory access")

    def test_blocks_command_with_shell_metacharacters(self) -> None:
        action = Action(
            type=ActionType.RUN_COMMAND,
            command=["python", "-m", "black", ".;cat", "secret"],
            target=str(self.root),
        )
        decision = self.engine.evaluate(action)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Command contains blocked shell metacharacters")

    def test_blocks_denied_executable(self) -> None:
        action = Action(
            type=ActionType.RUN_COMMAND,
            command=["curl", "https://example.com"],
            target=str(self.root),
        )
        decision = self.engine.evaluate(action)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Command explicitly blocked")

    def test_blocks_command_target_outside_project(self) -> None:
        outside_dir = self.root.parent
        action = Action(
            type=ActionType.RUN_COMMAND,
            command=["python", "-m", "black", "."],
            target=str(outside_dir),
        )
        decision = self.engine.evaluate(action)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "Path escapes project root")


if __name__ == "__main__":
    unittest.main()
