# Secure AI Agent (OpenClaw + ArmorClaw-style Policy)

Production-style autonomous developer assistant with strict, deterministic runtime policy enforcement.

## Core Goal

Enable autonomous project maintenance actions while preventing unsafe operations.

## Capabilities

Allowed actions include:

- project cleanup
- temporary file deletion
- formatter/linter command execution
- repository reorganization
- commit message generation

Blocked actions include:

- secret file access (for example .env)
- protected directory modifications (for example config, database)
- privileged or disallowed commands
- path traversal outside project root

## Architecture

1. Reasoning Layer: interpret user prompt and infer intent type.
2. Intent Parsing Layer: create strict structured intent schema.
3. Planning Layer: generate atomic action objects.
4. Policy Enforcement Layer: evaluate each action deterministically.
5. Execution Layer: execute only allowed actions.
6. Logging Layer: capture end-to-end trace.

See docs/architecture.md for details and diagram.

## Quick Start

1. Open a terminal at project root.
2. Run:

```bash
python demo/demo_run.py
```

The demo prints policy decisions and generates an audit trace at:

- demo/logs/demo_trace.jsonl

## LLM Reasoning Configuration

`ReasoningLayer` now uses a real OpenAI-compatible JSON adapter when credentials
are present, while keeping a deterministic fallback for offline reliability.

Set the following environment variables to enable live LLM reasoning:

- OPENAI_API_KEY: required API key
- OPENAI_MODEL: optional model name (default: gpt-4o-mini)
- OPENAI_BASE_URL: optional custom API base URL
