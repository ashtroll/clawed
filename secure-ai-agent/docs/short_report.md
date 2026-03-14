# Short Report: ARMORIQ x OPENCLAW Hackathon Submission

## Project Title
Secure Autonomous Developer Assistant with Runtime Intent Enforcement

## 1. Problem We Solved
Autonomous agents can perform real system actions, which introduces risk when instructions are vague. We built a system that preserves autonomy while enforcing strict, user-defined control at runtime.

## 2. System Objective
Enable meaningful multi-step autonomous execution on a local repository while guaranteeing deterministic blocking of unauthorized behavior.

## 3. Architecture Summary
The system is organized into explicit layers:

1. Reasoning Layer: Interprets user prompt and maps it to structured intent.
2. Intent Parsing Layer: Converts prompt into validated intent schema.
3. Planning Layer: Produces atomic executable actions.
4. Policy Enforcement Layer: Validates each action against policy constraints.
5. Execution Layer: Executes only policy-approved actions.
6. Logging Layer: Records full trace of intent, decisions, and outcomes.

Pipeline: User Prompt -> Intent -> Plan -> Policy Check -> Execution -> Logs

## 4. Intent Model
We use a structured intent object with clear fields:

1. intent type
2. target directory
3. allowed action categories
4. reasoning summary

This prevents unbounded interpretation of vague requests.

## 5. Policy Model
We enforce explicit, machine-checkable rules including:

1. allowed directories
2. protected files (for example: .env, credentials)
3. protected directories (for example: config, database)
4. allowed command list
5. blocked command list
6. blocked shell metacharacters
7. project-root confinement

## 6. Enforcement Mechanism
Every action is checked before execution. Decision outcomes are deterministic:

1. If compliant: action is executed
2. If non-compliant: action is blocked with explicit reason

No action bypasses the policy layer.

## 7. Real Execution Demonstrated
The agent performs real system operations such as:

1. deleting temporary directories
2. running formatter or linter commands
3. repository-safe maintenance tasks

## 8. Required Allowed/Blocked Demonstration
During demo run:

1. Allowed action: delete temporary folder
2. Blocked action: delete protected .env file
3. Block reason: protected file access

This proves runtime enforcement is active and observable.

## 9. Trust and Safety Guarantees
The system prevents:

1. command injection: no shell execution and metacharacter blocking
2. directory traversal: canonical path checks against project root
3. unauthorized access: protected file and folder enforcement
4. policy bypass: mandatory per-action policy validation

## 10. Observability and Traceability
Each run logs:

1. user intent
2. structured intent
3. planned actions
4. policy decisions per action
5. execution result or block reason

This provides auditable evidence for all autonomous behavior.

## 11. Outcome
The project satisfies the core hackathon requirements:

1. clear separation of reasoning and execution
2. explicit enforcement layer
3. real autonomous actions
4. deterministic blocking of violations
5. transparent, explainable runtime traceability
