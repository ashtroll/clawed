"""ArmorIQ intent verification — powered by the official armoriq-sdk.

Two-phase enforcement per run:

  Phase 1  sign_plan(prompt, intent, actions)
           Submits the full action plan to ArmorIQ before a single action
           executes.  ArmorIQ returns a cryptographically signed IntentToken
           whose plan_hash commits to every step.

  Phase 2  verify_action(action, intent_name)
           Checks each action against the signed token before execution.
           Any action whose type was not in the signed plan is rejected with
           an IntentMismatch verdict.

When ARMORIQ_API_KEY is not set the client falls back to a deterministic
local intent-alignment check so enforcement is never silently skipped.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from models.action_schema import Action, ActionType


@dataclass(frozen=True)
class ArmorClawDecision:
    """Immutable verdict returned by ArmorIQ (API or local fallback)."""

    approved: bool
    reason: str
    verified_by: str  # "armoriq_api" | "local_fallback"
    trace_id: str = ""
    plan_hash: str = ""


# Local intent-alignment map used when the API is unavailable.
_INTENT_ALLOWED_TYPES: dict[str, set[ActionType]] = {
    "project_cleanup":          {ActionType.DELETE, ActionType.CLEAN_DIRECTORY, ActionType.RUN_COMMAND},
    "code_quality_maintenance": {ActionType.RUN_COMMAND},
    "project_reorganization":   {ActionType.MOVE, ActionType.CLEAN_DIRECTORY},
    "commit_message_generation":{ActionType.GENERATE_COMMIT_MESSAGE},
    "generic_project_operation": set(ActionType),
}


class ArmorClawClient:
    """
    ArmorIQ intent verification client.

    Environment variables
    ---------------------
    ARMORIQ_API_KEY    Required for live ArmorIQ verification.
    ARMORIQ_USER_ID    User identifier sent to ArmorIQ (default: clawed-user).
    ARMORIQ_AGENT_ID   Agent identifier sent to ArmorIQ (default: clawed-agent).
    """

    def __init__(self) -> None:
        self.api_key  = os.getenv("ARMORIQ_API_KEY", "").strip()
        self.user_id  = os.getenv("ARMORIQ_USER_ID",  "clawed-user")
        self.agent_id = os.getenv("ARMORIQ_AGENT_ID", "clawed-developer-agent")

        # Set by sign_plan(); used by verify_action()
        self._token: Optional[object]    = None
        self._signed_types: List[str]    = []

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    # ------------------------------------------------------------------
    # Phase 1 — sign the plan
    # ------------------------------------------------------------------

    def sign_plan(
        self,
        prompt: str,
        intent_name: str,
        actions: List[Action],
    ) -> Optional[str]:
        """
        Submit the full action plan to ArmorIQ and receive a signed IntentToken.

        Returns the token_id string on success, or None when unconfigured /
        the API call fails.  The token is stored internally for verify_action().
        """
        if not self.is_configured:
            return None

        try:
            from armoriq_sdk import ArmorIQClient  # type: ignore

            steps = [
                {
                    "action": a.type.value,
                    "mcp":    "clawed-executor",
                    "params": {k: v for k, v in a.to_dict().items() if v is not None},
                }
                for a in actions
            ]

            with ArmorIQClient(
                api_key=self.api_key,
                user_id=self.user_id,
                agent_id=self.agent_id,
            ) as client:
                plan_capture = client.capture_plan(
                    llm="clawed-agent",
                    prompt=prompt,
                    plan={"goal": intent_name, "steps": steps},
                )
                self._token = client.get_intent_token(
                    plan_capture, validity_seconds=120
                )

            self._signed_types = [s["action"] for s in steps]
            return self._token.token_id  # type: ignore[union-attr]

        except Exception:
            self._token = None
            self._signed_types = []
            return None

    # ------------------------------------------------------------------
    # Phase 2 — verify each action
    # ------------------------------------------------------------------

    def verify_action(self, action: Action, intent_name: str) -> ArmorClawDecision:
        """
        Verify a single action.

        Uses the ArmorIQ-signed token when available; otherwise runs the
        local intent-alignment fallback.
        """
        if self._token is not None:
            return self._token_verify(action)
        return self._local_fallback(action, intent_name)

    # keep the old validate() name so existing call sites still work
    def validate(self, action: Action, intent_name: str, policy=None) -> ArmorClawDecision:
        return self.verify_action(action, intent_name)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _token_verify(self, action: Action) -> ArmorClawDecision:
        token = self._token
        plan_hash = getattr(token, "plan_hash", "")
        token_id  = getattr(token, "token_id",  str(uuid.uuid4()))

        if getattr(token, "is_expired", False):
            return ArmorClawDecision(
                approved=False,
                reason="ArmorIQ intent token has expired",
                verified_by="armoriq_api",
                trace_id=token_id,
                plan_hash=plan_hash,
            )

        if action.type.value in self._signed_types:
            return ArmorClawDecision(
                approved=True,
                reason=(
                    f"Action '{action.type.value}' verified against ArmorIQ "
                    f"signed intent token (plan_hash: {plan_hash[:16]}…)"
                ),
                verified_by="armoriq_api",
                trace_id=token_id,
                plan_hash=plan_hash,
            )

        return ArmorClawDecision(
            approved=False,
            reason=(
                f"IntentMismatch — '{action.type.value}' was not in the "
                f"ArmorIQ-signed plan (token: {token_id})"
            ),
            verified_by="armoriq_api",
            trace_id=token_id,
            plan_hash=plan_hash,
        )

    @staticmethod
    def _local_fallback(action: Action, intent_name: str) -> ArmorClawDecision:
        """Deterministic intent-alignment check used when no API key is set."""
        allowed = _INTENT_ALLOWED_TYPES.get(intent_name, set())

        if action.type not in allowed:
            return ArmorClawDecision(
                approved=False,
                reason=(
                    f"Action '{action.type.value}' is not aligned with "
                    f"intent '{intent_name}' (local fallback)"
                ),
                verified_by="local_fallback",
                trace_id=str(uuid.uuid4()),
            )

        return ArmorClawDecision(
            approved=True,
            reason=(
                f"Action '{action.type.value}' is consistent with "
                f"intent '{intent_name}' (local fallback)"
            ),
            verified_by="local_fallback",
            trace_id=str(uuid.uuid4()),
        )
