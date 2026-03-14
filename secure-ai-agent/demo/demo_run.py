from __future__ import annotations

import sys
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env so ARMORIQ_API_KEY is set before any module imports it
import os as _os
_env = PROJECT_ROOT / ".env"
if _env.exists():
    for _l in _env.read_text().splitlines():
        if _l.strip() and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            _os.environ.setdefault(_k.strip(), _v.strip())

from agents.developer_agent import SecureDeveloperAgent
from agents.sub_agent import DelegatedSubAgent
from models.delegation_schema import DelegationScope
from models.policy_schema import Policy


# ---------------------------------------------------------------------------
# Demo project setup
# ---------------------------------------------------------------------------

def create_demo_project(demo_root: Path) -> None:
    if demo_root.exists():
        shutil.rmtree(demo_root)

    (demo_root / "tmp").mkdir(parents=True, exist_ok=True)
    (demo_root / "config").mkdir(parents=True, exist_ok=True)
    (demo_root / "database").mkdir(parents=True, exist_ok=True)
    (demo_root / "src").mkdir(parents=True, exist_ok=True)

    (demo_root / "tmp" / "temp.txt").write_text("temporary artifact\n", encoding="utf-8")
    (demo_root / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    (demo_root / "config" / "settings.yaml").write_text("safe_mode: true\n", encoding="utf-8")
    (demo_root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")


def build_policy(demo_root: Path) -> Policy:
    return Policy(
        project_root=str(demo_root),
        allowed_directories=[str(demo_root)],
        protected_files=[".env", "credentials", "secret", "keys"],
        protected_directories=[str(demo_root / "config"), str(demo_root / "database")],
        allowed_commands=["python", "black", "eslint", "isort", "ruff", "git"],
        blocked_commands=["sudo", "chmod", "curl", "wget", "powershell", "cmd"],
    )


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------

_SEPARATOR = "=" * 60


def _section(title: str) -> None:
    print(f"\n{_SEPARATOR}")
    print(f"  {title}")
    print(_SEPARATOR)


def print_outcomes(outcomes: list[dict[str, object]]) -> None:
    for item in outcomes:
        action = item["action"]
        action_type = action["type"]
        target = action.get("path") or action.get("target") or action.get("source") or "—"
        gate = item.get("gate", "")
        gate_label = f" [{gate}]" if gate else ""

        if item["status"] == "executed":
            print(f"  ALLOWED{gate_label}: {action_type} -> {target}")
        else:
            print(f"  BLOCKED{gate_label}: {action_type} -> {target}")
            print(f"    Reason: {item['reason']}")


# ---------------------------------------------------------------------------
# Demo 1: Main agent — local policy + ArmorClaw enforcement
# ---------------------------------------------------------------------------

def demo_main_agent(demo_root: Path, policy: Policy) -> None:
    _section("DEMO 1 — Main Agent (Local Policy + ArmorClaw Verification)")

    agent = SecureDeveloperAgent(policy)
    prompt = "Clean the project, delete temporary files, and run formatting."

    print(f"\nPrompt: \"{prompt}\"\n")

    result = agent.run(prompt)

    print("Execution trace:")
    print(result["log_report"])

    print("\nPolicy + ArmorClaw outcomes:")
    print_outcomes(result["outcomes"])

    log_output = HERE / "logs" / "demo_main_trace.jsonl"
    agent.logger.write_jsonl(log_output)
    print(f"\nAudit trace saved to: {log_output}")


# ---------------------------------------------------------------------------
# Demo 2: Delegated sub-agent — delegation scope enforcement
# ---------------------------------------------------------------------------

def demo_delegation(demo_root: Path, policy: Policy) -> None:
    _section("DEMO 2 — Delegated Sub-Agent (Bounded Delegation)")

    print("""
Parent agent delegates a format-only task to a sub-agent.
Delegation scope: action type = run_command, commands = [black, ruff] only.

The sub-agent will attempt to:
  1. Delete a temp file          -> BLOCKED at the delegation gate
  2. Run black (formatter)       -> passes delegation, policy, and ArmorClaw
""")

    # The planner emits "python -m black", so "python" must be in the scope.
    # Broader command restrictions (only black/ruff flags) are enforced by
    # the blocked_substrings rule in the inherited policy.
    scope = DelegationScope(
        allowed_action_types=["run_command"],
        allowed_commands=["python", "black", "ruff"],
        allowed_directories=[str(demo_root)],
        delegated_by="SecureDeveloperAgent",
        reason="Format-only delegation: sub-agent may invoke black/ruff, nothing else",
    )

    sub_agent = DelegatedSubAgent(parent_policy=policy, delegation_scope=scope)

    # Prompt triggers both delete_temp_files (DELETE) and format_code (RUN_COMMAND).
    # DELETE must be stopped at the delegation gate; RUN_COMMAND should pass.
    prompt = "Clean the project and run formatting."
    print(f"Prompt: \"{prompt}\"\n")

    result = sub_agent.run(prompt)

    print("Execution trace:")
    print(result["log_report"])

    print("\nDelegation + Policy + ArmorClaw outcomes:")
    print_outcomes(result["outcomes"])

    log_output = HERE / "logs" / "demo_delegation_trace.jsonl"
    sub_agent.logger.write_jsonl(log_output)
    print(f"\nAudit trace saved to: {log_output}")


# ---------------------------------------------------------------------------
# Demo 3: ArmorClaw blocks an intent-misaligned action directly
# ---------------------------------------------------------------------------

def demo_armorclaw_block(demo_root: Path, policy: Policy) -> None:
    _section("DEMO 3 — ArmorClaw Blocks Intent-Misaligned Action")

    print("""
Direct call to ArmorClawClient.validate() to show the enforcement contract.
Action: DELETE  |  Declared intent: commit_message_generation
Local policy would allow the path—ArmorClaw rejects it as misaligned.
""")

    from models.action_schema import Action, ActionType
    from core.armorclaw import ArmorClawClient

    client = ArmorClawClient()
    misaligned_action = Action(
        type=ActionType.DELETE,
        path=str(demo_root / "tmp"),
    )
    intent_name = "commit_message_generation"

    decision = client.validate(misaligned_action, intent_name, policy)

    print(f"  Action:      {misaligned_action.type.value} -> {misaligned_action.path}")
    print(f"  Intent:      {intent_name}")
    print(f"  Approved:    {decision.approved}")
    print(f"  Reason:      {decision.reason}")
    print(f"  Verified by: {decision.verified_by}")
    print(f"  Trace ID:    {decision.trace_id}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    demo_root = HERE / "demo_project"
    create_demo_project(demo_root)
    policy = build_policy(demo_root)

    demo_main_agent(demo_root, policy)
    demo_delegation(demo_root, policy)
    demo_armorclaw_block(demo_root, policy)

    _section("DEMO COMPLETE")
    print("\nAll three demos finished. Audit traces saved to demo/logs/")


if __name__ == "__main__":
    main()
