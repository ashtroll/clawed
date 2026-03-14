# Clawed — Submission Document
## ArmorIQ x OpenClaw Hackathon

---

## 1. Project Summary

**Clawed** is a secure autonomous developer assistant that enforces user intent at every step of execution. It performs real filesystem and subprocess actions—but only after passing through a dual enforcement gate: a local policy engine and an independent ArmorClaw intent verifier. No action reaches the executor unless both gates explicitly approve it.

**Domain:** Developer tooling — autonomous project maintenance (cleanup, formatting, reorganization, commit message generation).

---

## 2. Intent Model

Intent is captured as a `StructuredIntent` dataclass emitted by the Intent Parsing Layer.

### Schema

| Field | Type | Description |
|---|---|---|
| `intent` | `str` | Named intent category (see values below) |
| `target_directory` | `str` | Absolute path the agent is permitted to operate in |
| `allowed_actions` | `List[str]` | Semantic action tokens inferred from the prompt |
| `raw_prompt` | `str` | Original user prompt, preserved for audit |
| `reasoning_summary` | `str` | Natural language explanation of how intent was inferred |

### Intent Categories

| Name | Meaning |
|---|---|
| `project_cleanup` | Remove temporary artifacts, improve hygiene |
| `code_quality_maintenance` | Run linters and formatters |
| `project_reorganization` | Move or restructure files and folders |
| `commit_message_generation` | Synthesize a commit message from git status |
| `generic_project_operation` | Catch-all with maximum policy gating |

### How Intent Is Inferred

The `ReasoningLayer` uses an OpenAI-compatible JSON adapter when `OPENAI_API_KEY` is set. It prompts the model to return a structured JSON object with `intent_name`, `target_directory`, and `reasoning_summary`. When credentials are absent, a deterministic keyword-matching fallback runs locally — ensuring intent validation is never skipped.

**This is not a hardcoded if-else check.** Intent is parsed into a typed `StructuredIntent` schema, validated by `.validate()`, and consumed by the planner as structured data — not raw strings.

---

## 3. Policy Model

Policy is defined as a `Policy` dataclass (ArmorClaw-style enforcement contract) and passed to every enforcement component at construction time.

### Schema

| Field | Type | Constraint type |
|---|---|---|
| `project_root` | `str` | Directory-scoped access |
| `allowed_directories` | `List[str]` | Directory-scoped access |
| `protected_files` | `List[str]` | Content / filename restrictions |
| `protected_directories` | `List[str]` | Directory-scoped access |
| `allowed_commands` | `List[str]` | Command restrictions (allow-list) |
| `blocked_commands` | `List[str]` | Command restrictions (deny-list) |
| `blocked_substrings` | `List[str]` | Command injection prevention |
| `max_command_runtime_seconds` | `int` | Time-based restrictions |

### Example Policy (from demo)

```json
{
  "project_root": "./demo_project",
  "allowed_directories": ["./demo_project"],
  "protected_files": [".env", "credentials", "secret", "keys"],
  "protected_directories": ["./demo_project/config", "./demo_project/database"],
  "allowed_commands": ["python", "black", "ruff", "isort", "eslint", "git"],
  "blocked_commands": ["sudo", "chmod", "curl", "wget", "powershell", "cmd"],
  "blocked_substrings": ["&&", ";", "|", "`", "$("],
  "max_command_runtime_seconds": 20
}
```

Policy is immutable (`frozen=True` dataclass) — it cannot be modified after construction, preventing runtime tampering.

---

## 4. Enforcement Mechanism

Every action passes through two independent enforcement gates before reaching the executor. Both gates must approve. Either gate can block independently.

### Gate 1 — Local PolicyEngine

Performs deterministic structural checks:

1. **Path bounds** — resolves all paths to canonical absolute form; rejects anything outside `project_root`
2. **Directory scope** — path must fall inside at least one `allowed_directory`
3. **Protected directory** — path must not be inside any `protected_directory`
4. **Protected file** — filename must not contain any `protected_files` token
5. **Command allow-list** — executable must be in `allowed_commands`
6. **Command deny-list** — executable must not be in `blocked_commands`
7. **Metacharacter filter** — command string must not contain any `blocked_substrings`
8. **Existence check** — target path must exist where required

Produces a `PolicyDecision(allowed: bool, reason: str)`.

### Gate 2 — ArmorClaw Verifier

Performs independent intent-alignment verification:

1. **API mode** — when `ARMORCLAW_API_KEY` is set, POSTs `{action, intent, policy}` to the ArmorClaw `/verify` endpoint and receives a verdict
2. **Local fallback** — when credentials are absent or the request fails, runs a deterministic intent-alignment check: verifies that the action's type is semantically consistent with the declared intent (e.g. `DELETE` is valid for `project_cleanup` but not for `commit_message_generation`)

Produces an `ArmorClawDecision(approved: bool, reason: str, verified_by: str, trace_id: str)`.

### Why Two Gates?

The local policy answers: **"Is this action structurally safe?"** (path bounds, command safety)

ArmorClaw answers: **"Is this action consistent with what the user actually asked for?"** (intent alignment)

A DELETE action on an allowed path would pass the local policy. But if the declared intent is `commit_message_generation`, ArmorClaw blocks it — the action is structurally safe but semantically wrong.

### Delegation Gate (Bonus)

When a `DelegatedSubAgent` is used, a third gate fires **before** both others:

- Checks that `action.type` is within the `DelegationScope.allowed_action_types`
- If not, blocks immediately with `gate: "delegation"` — the action never reaches the policy engine or ArmorClaw

The delegation scope is validated at construction time against the parent policy. It is impossible to create a sub-agent with more authority than its parent.

---

## 5. Separation of Reasoning and Execution

| Component | Role | Can execute? |
|---|---|---|
| `ReasoningLayer` | Infers intent from prompt | No |
| `IntentParser` | Produces `StructuredIntent` | No |
| `ActionPlanner` | Produces `Action` list | No |
| `PolicyEngine` | Evaluates each `Action` | No |
| `ArmorClawClient` | Verifies intent alignment | No |
| `OpenClawExecutor` | Performs filesystem/subprocess actions | Yes — only after both gates pass |

The `OpenClawExecutor` has no access to the policy, no awareness of intent, and no decision-making logic. It receives only pre-approved `Action` objects.

---

## 6. Delegation Scenario

**Scenario:** The parent `SecureDeveloperAgent` delegates a format-only task to a `DelegatedSubAgent`.

**Delegation scope granted:**
- Action types: `run_command` only
- Commands: `python`, `black`, `ruff` only
- Directories: same as parent

**What the sub-agent attempts:**
1. DELETE `./tmp` — **blocked at delegation gate** (DELETE not in granted action types)
2. DELETE `./.env` — **blocked at delegation gate** (DELETE not in granted action types)
3. RUN `python -m black .` — **passes all 3 gates**, formatter executes

**What this demonstrates:**
- The sub-agent's plan includes DELETE actions (which the parent could perform)
- The delegation gate stops them before policy or ArmorClaw are even consulted
- The formatter succeeds because `run_command` is in scope, `python`/`black` are in scope, and the intent aligns

---

## 7. Observability

Every run produces a complete `JSONL` audit trace with one record per pipeline stage:

| Stage | What is logged |
|---|---|
| `user_intent` | Raw user prompt |
| `structured_intent` | Full `StructuredIntent` fields |
| `agent_plan` | All planned `Action` objects |
| `delegation_check` | Delegation gate verdict (sub-agent only) |
| `policy_check` | `PolicyDecision` with reason |
| `armorclaw_check` | `ArmorClawDecision` with trace_id and verified_by |
| `execution_result` | Gate that blocked, or execution result |
| `execution_summary` | All outcomes combined |

Each outcome includes a `gate` field that names which enforcement layer made the final decision: `delegation`, `local_policy`, `armorclaw`, or `all_passed`.

---

## 8. File Structure

```
secure-ai-agent/
├── agents/
│   ├── developer_agent.py     # Main orchestrator — 3-gate pipeline
│   └── sub_agent.py           # Delegated sub-agent — 4-gate pipeline
├── core/
│   ├── armorclaw.py           # ArmorClaw API client + local fallback
│   ├── executor.py            # OpenClawExecutor — real filesystem actions
│   ├── intent_parser.py       # StructuredIntent emitter
│   ├── logger.py              # Immutable JSONL audit logger
│   ├── planner.py             # Typed Action plan builder
│   ├── policy_engine.py       # Deterministic policy enforcement
│   └── reasoning.py           # LLM reasoning layer + deterministic fallback
├── models/
│   ├── action_schema.py       # Action, ActionType, PolicyDecision
│   ├── delegation_schema.py   # DelegationScope
│   ├── intent_schema.py       # StructuredIntent
│   └── policy_schema.py       # Policy (ArmorClaw-style contract)
├── demo/
│   ├── demo_run.py            # Three demo scenarios
│   └── logs/                  # JSONL audit traces (generated on run)
├── docs/
│   ├── architecture.md        # Architecture diagram (Mermaid)
│   └── submission.md          # This document
└── tests/
    └── test_policy_engine.py  # Unit tests for enforcement edge cases
```
