# Clawed — Architecture Diagram

## Full Execution Pipeline

```mermaid
flowchart TD
    U(["👤 User Prompt\n'Clean the project and run formatting'"])

    subgraph REASONING ["Layer 1 — Reasoning"]
        R["ReasoningLayer\nOpenAI-compatible JSON adapter\n(deterministic fallback when offline)"]
    end

    subgraph PARSING ["Layer 2 — Intent Parsing"]
        I["IntentParser\nEmits StructuredIntent schema\n• intent name\n• target_directory\n• allowed_actions list"]
    end

    subgraph PLANNING ["Layer 3 — Action Planning"]
        P["ActionPlanner\nBuilds typed atomic Action objects\n• DELETE  • CLEAN_DIRECTORY\n• RUN_COMMAND  • MOVE\n• GENERATE_COMMIT_MESSAGE"]
    end

    subgraph ENFORCEMENT ["Layer 4 — Dual Enforcement Gate"]
        PE["Local PolicyEngine\n• Path bounds check\n• Protected file / dir check\n• Command allow-list + deny-list\n• Shell metacharacter filter"]
        AC["ArmorClaw Verifier\n• API call (when key is set)\n• Local intent-alignment fallback\n• Checks action type vs declared intent\n• Returns ArmorClawDecision + trace_id"]
    end

    subgraph DELEGATION ["Delegation Layer (Bonus)"]
        DG["DelegationScope Gate\n• Checked BEFORE policy\n• Blocks action types outside granted scope\n• Scope validated ⊆ parent policy at init"]
        SA["DelegatedSubAgent\nNarrowed Policy + 4-gate pipeline\nDelegation → Policy → ArmorClaw → Execute"]
    end

    subgraph EXECUTION ["Layer 5 — Execution"]
        EX["OpenClawExecutor\n• File delete / move / clean\n• subprocess (shell=False)\n• Timeout enforcement"]
    end

    subgraph LOGGING ["Layer 6 — Logging & Audit"]
        LOG["PipelineLogger\nImmutable JSONL trace\nEvery stage: intent → plan\n→ policy → armorclaw → result"]
    end

    B(["🚫 BLOCKED\nReason + gate recorded"])
    A(["✅ EXECUTED\nResult recorded"])

    U --> REASONING
    REASONING --> PARSING
    PARSING --> PLANNING
    PLANNING --> ENFORCEMENT

    PE -->|"blocked"| B
    PE -->|"allowed"| AC
    AC -->|"blocked"| B
    AC -->|"approved"| EX

    PLANNING -.->|"delegation path"| DG
    DG -->|"out of scope"| B
    DG -->|"in scope"| SA

    EX --> A
    A --> LOGGING
    B --> LOGGING
```

---

## Data Flow: Key Schemas

### StructuredIntent (output of Layer 2)
```json
{
  "intent": "project_cleanup",
  "target_directory": "./demo_project",
  "allowed_actions": ["delete_temp_files", "format_code"],
  "raw_prompt": "Clean the project and run formatting.",
  "reasoning_summary": "User asked to remove temporary artifacts and improve repository hygiene."
}
```

### Action (output of Layer 3)
```json
{
  "type": "delete",
  "path": "./demo_project/tmp",
  "command": null,
  "target": null,
  "source": null,
  "destination": null
}
```

### Policy (ArmorClaw-style enforcement contract)
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

### ArmorClawDecision (output of Layer 4 gate 2)
```json
{
  "approved": true,
  "reason": "Action 'delete' is consistent with intent 'project_cleanup'",
  "verified_by": "local_fallback",
  "trace_id": "1d9a3a6b-c28e-4387-863f-5c7eb4722b2c"
}
```

### DelegationScope
```json
{
  "allowed_action_types": ["run_command"],
  "allowed_commands": ["python", "black", "ruff"],
  "allowed_directories": ["./demo_project"],
  "delegated_by": "SecureDeveloperAgent",
  "reason": "Format-only delegation: sub-agent may invoke formatters, nothing else"
}
```

---

## Enforcement Decision Tree (per action)

```
Action proposed by Planner
│
├─[if DelegatedSubAgent]─► Delegation Gate
│     action.type ∈ granted_action_types?
│     NO  → BLOCKED (gate: delegation)
│     YES → continue
│
├─► Local PolicyEngine
│     path within project_root? → path in allowed_dirs? → not protected? → command in allow-list?
│     ANY FAIL → BLOCKED (gate: local_policy)
│     ALL PASS → continue
│
├─► ArmorClaw Verifier
│     action.type consistent with intent_name?
│     (API call if key set, else local fallback)
│     NO  → BLOCKED (gate: armorclaw)
│     YES → continue
│
└─► OpenClawExecutor  →  EXECUTED (gate: all_passed)
```
