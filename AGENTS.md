# AGENTS.md

## Project

Project name: **CartCare**

Positioning: **E-commerce Support Agent**

CartCare is a resume project for Agent / LLM application engineering roles.

The goal is not to maximize the number of AI features. The goal is to build a coherent, explainable, testable customer-support Agent system with clear boundaries between:

- LLM reasoning and deterministic business rules
- RAG knowledge and live business data
- read-only tools and state-changing actions
- autonomous execution and human approval

## Source of truth

When determining the current state of the project, use this priority:

1. Executable code and real call paths
2. Automated tests and actual runtime results
3. `docs/CartCare-Codex-Workbench.html`
4. `docs/cartcare-workbench-progress.json` if present
5. README / Wiki / architecture diagrams
6. Historical notes

If documentation conflicts with executable code, treat the code as authoritative and report the documentation drift.

Do not infer that a capability is active only because a file, class, function, or README section exists.
Verify that it is connected to an executable path.

## Collaboration workspace

Before starting a non-trivial task, read:

- `docs/CartCare-Codex-Workbench.html`
- `docs/cartcare-workbench-progress.json` if it exists

The workbench records:

- verified current-state baseline
- target architecture
- P0 / P1 / P2 / P3 roadmap
- task IDs and status
- design decisions
- acceptance criteria
- verification notes

`AGENTS.md` contains stable collaboration rules.
The workbench contains changing project state and progress.

## Architecture principles

### RAG vs live business data

Use RAG for static or semi-static knowledge such as:

- FAQ
- refund policy
- shipping policy
- after-sales rules
- product documentation
- membership rules

Use Provider / Repository / API / DB abstractions for dynamic facts such as:

- order status
- shipment status
- inventory
- payment status
- refund status
- customer-owned order data

Never use RAG to fabricate live business state.

### LLM vs deterministic logic

The LLM / Agent may handle:

- intent understanding
- clarification
- tool selection
- parameter collection
- limited multi-step planning
- response generation

Deterministic code must handle hard constraints such as:

- refund eligibility
- cancellation eligibility
- amount limits
- permissions
- ownership checks
- state transitions
- idempotency
- risk gates

Do not encode non-negotiable business rules only in prompts.

### High-risk actions

State-changing or sensitive actions must follow a controlled path:

Agent request
→ Tool request
→ Policy / Permission Gate
→ Human approval when required
→ Action execution
→ Auditable result

The LLM must not directly guarantee that a refund, cancellation, or other business mutation has succeeded.

### Multi-Agent

Do not assume Multi-Agent is better.

Evaluate simpler alternatives first:

- single Agent + tools
- single Agent + deterministic workflows
- supervisor + specialists
- multi-Agent

Keep multiple Agents only when domain boundaries, tool sets, state machines, or measurable outcomes justify the added complexity.

## Scope discipline

Work on the task requested.

Do not expand a task into unrelated refactors.

If you discover technical debt outside the current task:

1. report it
2. record it as a follow-up
3. do not modify it unless required to complete the current task

Avoid replacing the whole Agent framework or introducing large dependencies unless the task explicitly requires it.

## Before modifying code

For a non-trivial task:

1. Read the workbench.
2. Inspect the relevant code and call path.
3. Check related tests.
4. Check `git status`.
5. Identify documentation drift.
6. State the planned files, risks, and validation approach.

Do not begin from assumptions based only on filenames or README claims.

## Tool and action rules

Prefer one consistent tool schema and execution path.

Tool design should distinguish at least:

- read
- write
- dangerous / approval-required

For state-changing tools, consider:

- strict input validation
- permission checks
- ownership
- timeout
- retry policy
- idempotency key
- duplicate execution
- typed errors
- auditable result

Mocks must be clearly identified as mocks.
Do not present mock behavior as a real external business integration.

## Testing

Code existence is not completion.

Where relevant, test:

- happy path
- invalid input
- dependency failure
- timeout
- business-rule rejection
- repeated request

For state-changing actions also test:

- idempotency
- duplicate execution
- approval bypass
- ownership violations

If tests cannot run, report the exact reason.
Do not claim success from unexecuted tests.

## Trace and observability

Record observable execution events such as:

- request_id
- routing result
- selected tool
- validated tool arguments
- tool result
- retrieval result and citations
- policy decision
- approval state
- latency
- error type

Do not persist or expose hidden model chain-of-thought.

## Evaluation

Prefer deterministic and task-specific metrics where possible.

Important evaluation areas include:

- routing accuracy
- tool selection accuracy
- tool argument correctness
- tool execution success
- retrieval Recall@K
- citation / grounding correctness
- task success
- policy violation rate
- missed escalation
- HITL correctness
- duplicate-action rate
- loop / max-step rate
- latency
- token usage / cost

Use LLM-as-Judge only where subjective response quality actually requires it.

## Task status

Workbench task states:

- `todo`: not started
- `doing`: implementation in progress
- `blocked`: real blocking dependency exists
- `verify`: implementation is complete enough for validation
- `done`: accepted after validation

After implementing a task, normally recommend `verify`, not `done`.

The user decides when a task is fully accepted.

## End-of-task report

After completing a task, report:

### Changed files
What changed and why.

### Call path
Before and after, if the execution path changed.

### Tests
Commands run, passed / failed counts, and anything that could not run.

### Acceptance criteria
Map results to the workbench DoD.

### Newly discovered issues
Report them without silently expanding scope.

### Documentation drift
State whether README, Wiki, architecture docs, or the workbench baseline should be updated.

### Suggested task state
Recommend `doing`, `blocked`, `verify`, or `done`, with a short reason.

### Suggested commit message
Provide one concise commit message.

## Branding compatibility

Public project branding is **CartCare**.

Legacy runtime identifiers may temporarily remain for compatibility, including names such as:

- `ECHOMIND_*`
- `echomind-app`
- `echomind-network`

Do not rename runtime identifiers as part of unrelated tasks.
Migrate them only in a dedicated compatibility task.

## Current project direction

CartCare should evolve into a system that is:

- grounded in realistic e-commerce support scenarios
- clear about Agent vs deterministic responsibility
- reliable in tool use
- safe for sensitive actions
- observable
- replayable
- measurable with repeatable evaluations
- simple enough to explain in an interview
- deep enough to demonstrate Agent engineering judgment

Prefer justified engineering decisions over feature count.
