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
from models.action_schema import Action
from models.policy_schema import Policy


class SecureDeveloperAgent:
    """
    End-to-end autonomous agent orchestrator.

    Execution pipeline
    ------------------
    User Prompt
        → [1] Reasoning Layer       (intent inference)
        → [2] Intent Parser         (structured intent schema)
        → [3] Action Planner        (atomic action list)
        → [4] Local Policy Engine   (path bounds, command allow-list)
        → [5] ArmorClaw Verifier    (independent intent-alignment check)
        → [6] Executor              (filesystem / subprocess actions)
        → [7] Logger                (immutable JSONL audit trace)
    """

    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self.logger = PipelineLogger()
        self.intent_parser = IntentParser(ReasoningLayer())
        self.planner = ActionPlanner()
        self.policy_engine = PolicyEngine(policy)
        self.armorclaw = ArmorClawClient()
        self.executor = OpenClawExecutor(policy)

    def run(self, user_prompt: str) -> Dict[str, object]:
        project_root = Path(self.policy.project_root).resolve()
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
        }

    def _process_action(self, action: Action, intent_name: str) -> Dict[str, object]:
        # --- Gate 1: Local policy engine ---
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

        # --- Gate 2: ArmorClaw intent verification ---
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

        # --- Gate 3: Execute ---
        result = self.executor.execute(action)
        executed = {
            "action": action.to_dict(),
            "status": "executed",
            "gate": "all_passed",
            "result": result,
        }
        self.logger.log("execution_result", executed)
        return executed
