# Clawed — Secure Autonomous Developer Agent

**ArmorIQ × OpenClaw Hackathon 2025**

Clawed is an intent-aware autonomous developer agent that enforces strict policy boundaries at runtime. Every action passes through a dual-gate enforcement stack before it reaches the system — making autonomous execution both capable and trustworthy.

## How It Works

A user prompt flows through a 7-layer pipeline:

1. **Reasoning** — infer structured intent from the prompt
2. **Intent Parsing** — produce a validated `StructuredIntent` schema
3. **Action Planning** — generate typed `Action` objects
4. **Gate 4a — Delegation** — block actions outside the sub-agent's granted scope
5. **Gate 4b — Local Policy** — enforce directory bounds, protected files, command lists
6. **Gate 4c — ArmorIQ Verifier** — verify intent alignment via the ArmorIQ live API
7. **Executor + Logger** — run approved actions and write an immutable JSONL audit trace

Reasoning never calls the executor directly. The enforcement stack cannot be bypassed.

## Key Features

- **Structured intent model** — `StructuredIntent` constrains which action types are permitted per run
- **Local policy enforcement** — directory scope, protected file tokens, command allow/deny lists
- **Live ArmorIQ integration** — every plan is signed (`token_id`, `plan_hash`) and each action is verified (`verified_by: armoriq_api`)
- **Bounded delegation** — `DelegationScope` grants sub-agents a strict subset of parent authority
- **Full audit trail** — every stage logged to immutable JSONL with gate, reason, and trace ID

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Add your ArmorIQ key to .env
echo "ARMORIQ_API_KEY=your_key_here" > .env

# Run the demo
python demo/demo_run.py
```

The demo runs three scenarios — cleanup, formatting, and commit message generation — showing both allowed and blocked actions with full gate reasoning.

## Demo Scenarios

| Scenario | Intent | Key Result |
|----------|--------|------------|
| Demo 1 | `project_cleanup` | DELETE /tmp ✅ · DELETE .env ❌ (local_policy) |
| Demo 2 | `code_formatting` | black formatter ✅ · sudo ❌ (local_policy) |
| Demo 3 | `generate_commit_message` | commit msg ✅ · DELETE ❌ (armorclaw) |

## Delegation Demo

```bash
python demo/demo_delegation.py
```

A `DelegatedSubAgent` receives format-only authority. Any attempt to delete files is blocked at Gate 4a before reaching policy or ArmorIQ.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `ARMORIQ_API_KEY` | ArmorIQ live API key (required for live verification) |
| `ARMORIQ_USER_ID` | Agent user identity |
| `ARMORIQ_AGENT_ID` | Agent identifier |
| `OPENAI_API_KEY` | Optional — enables LLM-based reasoning (falls back to deterministic) |
