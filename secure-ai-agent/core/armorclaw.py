"""ArmorClaw intent verification client.

Sends each proposed action + its declared intent to the ArmorClaw enforcement
API for independent runtime validation before the executor fires.

When the API is unavailable (no key or network error) the client falls back to
a local structured intent-alignment check that verifies the action type is
consistent with the declared intent—ensuring enforcement is never silently
skipped.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from models.action_schema import Action, ActionType
from models.policy_schema import Policy


@dataclass(frozen=True)
class ArmorClawDecision:
    """Immutable verdict returned by ArmorClaw (API or local fallback)."""

    approved: bool
    reason: str
    verified_by: str  # "armorclaw_api" | "local_fallback"
    trace_id: str = ""


# Maps each intent name to the action types that are semantically consistent
# with that intent.  Any action whose type is absent from this set is
# considered intent-misaligned and will be rejected.
_INTENT_ALLOWED_TYPES: dict[str, set[ActionType]] = {
    "project_cleanup": {
        ActionType.DELETE,
        ActionType.CLEAN_DIRECTORY,
        ActionType.RUN_COMMAND,         # formatters are part of cleanup
    },
    "code_quality_maintenance": {
        ActionType.RUN_COMMAND,
    },
    "project_reorganization": {
        ActionType.MOVE,
        ActionType.CLEAN_DIRECTORY,
    },
    "commit_message_generation": {
        ActionType.GENERATE_COMMIT_MESSAGE,
    },
    "generic_project_operation": set(ActionType),   # all types permitted
}


class ArmorClawClient:
    """
    Verifies that each planned action is aligned with the declared user intent.

    Two-tier enforcement:
    1. Live API call when ARMORCLAW_API_KEY is configured.
    2. Deterministic local fallback when credentials are absent or the request
       fails—guaranteeing the enforcement layer is never bypassed.

    Environment variables
    ---------------------
    ARMORCLAW_API_KEY   Required for live API verification.
    ARMORCLAW_BASE_URL  Optional custom endpoint (default: https://api.armorclaw.io/v1).
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("ARMORCLAW_API_KEY", "").strip()
        self.base_url = (
            os.getenv("ARMORCLAW_BASE_URL", "https://api.armorclaw.io/v1")
            .strip()
            .rstrip("/")
        )

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def validate(
        self,
        action: Action,
        intent_name: str,
        policy: Policy,
    ) -> ArmorClawDecision:
        """Return an ArmorClaw verdict for the (action, intent, policy) triple."""
        if not self.is_configured:
            return self._local_fallback(action, intent_name)

        try:
            return self._api_validate(action, intent_name, policy)
        except RuntimeError:
            # Network or parse error → fall back rather than blocking silently.
            return self._local_fallback(action, intent_name)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _api_validate(
        self,
        action: Action,
        intent_name: str,
        policy: Policy,
    ) -> ArmorClawDecision:
        """POST to the ArmorClaw /verify endpoint and parse the response."""
        payload: dict[str, Any] = {
            "action": action.to_dict(),
            "intent": intent_name,
            "policy": {
                "project_root": policy.project_root,
                "allowed_directories": policy.allowed_directories,
                "protected_files": policy.protected_files,
                "protected_directories": policy.protected_directories,
                "allowed_commands": policy.allowed_commands,
                "blocked_commands": policy.blocked_commands,
            },
        }

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/verify",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=10) as response:
                raw = response.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(f"ArmorClaw API request failed: {exc}") from exc

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("ArmorClaw returned invalid JSON") from exc

        return ArmorClawDecision(
            approved=bool(result.get("approved", False)),
            reason=str(result.get("reason", "")),
            verified_by="armorclaw_api",
            trace_id=str(result.get("trace_id", "")),
        )

    @staticmethod
    def _local_fallback(action: Action, intent_name: str) -> ArmorClawDecision:
        """
        Deterministic intent-alignment check used when the API is unavailable.

        Checks that the action type is semantically consistent with the
        declared intent—catching cases where a planning layer tries to
        smuggle an action type outside the user's stated goal.
        """
        allowed_types = _INTENT_ALLOWED_TYPES.get(intent_name, set())

        if action.type not in allowed_types:
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
