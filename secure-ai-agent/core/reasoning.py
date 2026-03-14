from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


@dataclass(frozen=True)
class ReasoningOutput:
    intent_name: str
    target_directory: str
    reasoning_summary: str


class _DeterministicReasoner:
    """Fallback strategy used when LLM configuration is unavailable."""

    @staticmethod
    def infer(user_prompt: str, project_root: Path) -> ReasoningOutput:
        text = user_prompt.lower()

        if "clean" in text or "cleanup" in text:
            intent_name = "project_cleanup"
            summary = "User asked to remove temporary artifacts and improve repository hygiene."
        elif "lint" in text or "format" in text:
            intent_name = "code_quality_maintenance"
            summary = "User requested linting/formatting actions constrained to project scope."
        elif "reorganize" in text or "reorganise" in text:
            intent_name = "project_reorganization"
            summary = "User requested structural file/folder reorganization in repository."
        elif "commit" in text and "message" in text:
            intent_name = "commit_message_generation"
            summary = "User requested commit message synthesis from local changes."
        else:
            intent_name = "generic_project_operation"
            summary = "Prompt mapped to generic project operation with strict policy gate."

        return ReasoningOutput(
            intent_name=intent_name,
            target_directory=str(project_root),
            reasoning_summary=summary,
        )


class JsonLLMReasoner:
    """
    OpenAI-compatible JSON adapter that returns strict structured intent fields.

    Environment variables:
    - OPENAI_API_KEY: API key for model access.
    - OPENAI_MODEL: model name (default: gpt-4o-mini).
    - OPENAI_BASE_URL: optional custom endpoint (default: https://api.openai.com/v1).
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def infer(self, user_prompt: str, project_root: Path) -> ReasoningOutput:
        if not self.is_configured:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        schema_hint = {
            "intent_name": "project_cleanup|code_quality_maintenance|project_reorganization|commit_message_generation|generic_project_operation",
            "target_directory": str(project_root),
            "reasoning_summary": "short security-aware explanation",
        }

        system_prompt = (
            "You are the reasoning layer for a secure autonomous developer agent. "
            "Return only valid JSON with keys intent_name, target_directory, reasoning_summary. "
            "Use one of the allowed intent_name values from the provided schema."
        )

        payload: dict[str, Any] = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Prompt: {user_prompt}\n"
                        f"Project root: {project_root}\n"
                        f"Schema: {json.dumps(schema_hint)}"
                    ),
                },
            ],
            "temperature": 0,
        }

        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8")
        except error.URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc}") from exc

        try:
            parsed = json.loads(raw)
            content = parsed["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            raise RuntimeError("LLM returned invalid JSON response") from exc

        intent_name = str(result.get("intent_name", "")).strip()
        target_directory = str(result.get("target_directory", project_root)).strip()
        reasoning_summary = str(result.get("reasoning_summary", "")).strip()

        if not intent_name:
            raise RuntimeError("LLM response missing intent_name")
        if not target_directory:
            raise RuntimeError("LLM response missing target_directory")
        if not reasoning_summary:
            raise RuntimeError("LLM response missing reasoning_summary")

        return ReasoningOutput(
            intent_name=intent_name,
            target_directory=target_directory,
            reasoning_summary=reasoning_summary,
        )


class ReasoningLayer:
    """
    Reasoning facade preserving a stable infer() interface.

    It prefers a real LLM JSON adapter and deterministically falls back to local
    heuristics when network credentials are not available.
    """

    def __init__(self) -> None:
        self.llm_reasoner = JsonLLMReasoner()
        self.fallback_reasoner = _DeterministicReasoner()

    def infer(self, user_prompt: str, project_root: Path) -> ReasoningOutput:
        try:
            return self.llm_reasoner.infer(user_prompt=user_prompt, project_root=project_root)
        except RuntimeError:
            return self.fallback_reasoner.infer(user_prompt=user_prompt, project_root=project_root)
