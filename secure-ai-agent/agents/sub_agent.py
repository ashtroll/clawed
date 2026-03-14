"""DelegatedSubAgent — a bounded-scope agent instantiated by a parent agent.

Demonstrates the delegation bonus requirement:
  * The parent grants a narrowed DelegationScope (limited action types +
    limited commands).
  * Delegation scope is validated to be a strict subset of the parent policy
    at construction time—privilege escalation is impossible.
  * Each action is checked against the delegation scope FIRST (before the
    local policy engine and ArmorClaw), so the enforcement chain is:

      [1] Delegation gate   ← checks action type is within granted scope
      [2] Local Policy      ← path bounds, command allow-list, etc.
      [3] ArmorClaw         ← intent-alignment verification
      [4] Executor          ← actual filesystem / subprocess action
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from core.armorclaw import ArmorClawClient
from core.executor import OpenClawExecutor
from core.intent_parser import IntentParser
from core.logger import PipelineLogger
from core.planner import ActionPlanner
from core.policy_engine import PolicyEngine
from core.reasoning import ReasoningLayer
from models.action_schema import Action, ActionType
from models.delegation_schema import DelegationScope
from models.policy_schema import Policy


class DelegatedSubAgent:
    """
    A sub-agent whose authority is strictly bounded by a DelegationScope.

    Usage
    -----
    scope = DelegationScope(
        allowed_action_types=["run_command"],
        allowed_commands=["black", "ruff"],
        allowed_directories=[str(project_root)],
        delegated_by="SecureDeveloperAgent",
        reason="Format-only delegation",
    )
    sub = DelegatedSubAgent(parent_policy, scope)
    result = sub.run("run black and ruff on the project")
    """

    def __init__(self, parent_policy: Policy, delegation_scope: DelegationScope) -> None:
        # Raises ValueError immediately if scope exceeds parent authority.
        delegation_scope.validate_against_parent(
            parent_policy.allowed_commands,
            parent_policy.allowed_directories,
        )

        self.delegation_scope = delegation_scope
        self._allowed_types = {ActionType(t) for t in delegation_scope.allowed_action_types}

        # Build a narrowed policy: inherit protections from parent, restrict
        # to the commands and directories granted by the scope.
        narrowed_policy = Policy(
            project_root=parent_policy.project_root,
            allowed_directories=(
                delegation_scope.allowed_directories
                if delegation_scope.allowed_directories
                else parent_policy.allowed_directories
            ),
            protected_files=parent_policy.protected_files,
            protected_directories=parent_policy.protected_directories,
            allowed_commands=(
                delegation_scope.allowed_commands
                if delegation_scope.allowed_commands
                else parent_policy.allowed_commands
            ),
            blocked_commands=parent_policy.blocked_commands,
            blocked_substrings=parent_policy.blocked_substrings,
            max_command_runtime_seconds=parent_policy.max_command_runtime_seconds,
        )

        self.policy = narrowed_policy
        self.logger = PipelineLogger()
        self.intent_parser = IntentParser(ReasoningLayer())
        self.planner = ActionPlanner()
        self.policy_engine = PolicyEngine(narrowed_policy)
        self.armorclaw = ArmorClawClient()
        self.executor = OpenClawExecutor(narrowed_policy)

    def run(self, user_prompt: str) -> Dict[str, object]:
        project_root = Path(self.policy.project_root).resolve()

        self.logger.log(
            "delegation_context",
            {
                "delegated_by": self.delegation_scope.delegated_by,
                "granted_action_types": self.delegation_scope.allowed_action_types,
                "granted_commands": self.delegation_scope.allowed_commands,
                "reason": self.delegation_scope.reason,
            },
        )
        self.logger.log("user_intent", {"prompt": user_prompt})

        intent = self.intent_parser.parse(user_prompt=user_prompt, project_root=project_root)
        self.logger.log(
            "structured_intent",
            {
                "intent": intent.intent,
                "target_directory": intent.target_directory,
                "allowed_actions": intent.allowed_actions,
                "reasoning_summary": intent.reasoning_summary,
            },
        )

        plan = self.planner.build_plan(intent)
        self.logger.log("agent_plan", {"actions": [a.to_dict() for a in plan]})

        outcomes: List[Dict[str, object]] = []
        for action in plan:
            outcomes.append(self._process_action(action, intent.intent))

        self.logger.log("execution_summary", {"outcomes": outcomes})

        return {
            "intent": intent,
            "plan": plan,
            "outcomes": outcomes,
            "log_report": self.logger.render_console_report(),
            "delegated_by": self.delegation_scope.delegated_by,
            "delegation_scope": {
                "allowed_action_types": self.delegation_scope.allowed_action_types,
                "allowed_commands": self.delegation_scope.allowed_commands,
                "reason": self.delegation_scope.reason,
            },
        }

    def _process_action(self, action: Action, intent_name: str) -> Dict[str, object]:
        # --- Gate 1: Delegation scope ---
        if action.type not in self._allowed_types:
            blocked = {
                "action": action.to_dict(),
                "status": "blocked",
                "gate": "delegation",
                "reason": (
                    f"[DELEGATION BLOCKED] Action type '{action.type.value}' is "
                    f"outside the scope delegated by '{self.delegation_scope.delegated_by}'. "
                    f"Granted types: {self.delegation_scope.allowed_action_types}"
                ),
            }
            self.logger.log("delegation_check", blocked)
            self.logger.log("execution_result", blocked)
            return blocked

        self.logger.log(
            "delegation_check",
            {
                "action": action.to_dict(),
                "allowed": True,
                "reason": f"Action type '{action.type.value}' is within delegated scope",
            },
        )

        # --- Gate 2: Local policy engine ---
        policy_decision = self.policy_engine.evaluate(action)
        self.logger.log(
            "policy_check",
            {
                "action": action.to_dict(),
                "allowed": policy_decision.allowed,
                "reason": policy_decision.reason,
            },
        )

        if not policy_decision.allowed:
            blocked = {
                "action": action.to_dict(),
                "status": "blocked",
                "gate": "local_policy",
                "reason": policy_decision.reason,
            }
            self.logger.log("execution_result", blocked)
            return blocked

        # --- Gate 3: ArmorClaw intent verification ---
        ac_decision = self.armorclaw.validate(action, intent_name, self.policy)
        self.logger.log(
            "armorclaw_check",
            {
                "action": action.to_dict(),
                "approved": ac_decision.approved,
                "reason": ac_decision.reason,
                "verified_by": ac_decision.verified_by,
                "trace_id": ac_decision.trace_id,
            },
        )

        if not ac_decision.approved:
            blocked = {
                "action": action.to_dict(),
                "status": "blocked",
                "gate": "armorclaw",
                "reason": ac_decision.reason,
            }
            self.logger.log("execution_result", blocked)
            return blocked

        # --- Gate 4: Execute ---
        result = self.executor.execute(action)
        executed = {
            "action": action.to_dict(),
            "status": "executed",
            "gate": "all_passed",
            "result": result,
        }
        self.logger.log("execution_result", executed)
        return executed
