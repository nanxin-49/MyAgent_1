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


## Wiki documentation policy

Do **not** maintain every file under `wiki/`.

Only the following Wiki documents are treated as core, actively maintained project documentation:

1. `wiki/CartCare定位与技术亮点.md`
   - explains what CartCare is
   - defines the business scope and positioning
   - summarizes the major architecture choices and technical highlights
   - should stay understandable to someone reading the project for the first time

2. `wiki/重点代码.md`
   - explains the real executable request path
   - maps important runtime behavior to concrete files, classes, and functions
   - should stay aligned with the current implementation

These two files are the primary Wiki documents for understanding the project.

Other files under `wiki/` are secondary or historical material, including documents such as:

- `CartCare学习文档.md`
- `NexusOps企业智能运营协同中枢.md`
- `带数据指标的加强版简历模板.md`
- `技术亮点.md`
- `架构图.md`
- `简历包装.md`
- `完整使用指南.md`
- `文档中心.md`
- `业务流程说明.md`

Do not automatically update those files as part of ordinary implementation tasks.

If one of them becomes materially misleading:

1. report the drift
2. mention which core document already contains the authoritative version
3. update the secondary document only when the user explicitly requests documentation cleanup

Do not duplicate the same architecture explanation across multiple Wiki files.

For normal code changes, documentation review should normally be limited to:

- `README.md`
- `docs/CartCare-Codex-Workbench.html` / progress JSON when project state changes
- `wiki/CartCare定位与技术亮点.md` when positioning or architecture changes
- `wiki/重点代码.md` when executable call paths or core module responsibilities change

## Collaboration workspace

Before starting a non-trivial task, read:

- `docs/CartCare-Codex-Workbench.html`
- `docs/cartcare-workbench-progress.json` if it exists
- `docs/hardening/README.md` and the **current** `docs/hardening/tasks/<Axx>.md` when working on post-T12 hardening (V3)
- only the **relevant C/N entries** of `docs/engineering/project-audit-20261011.md` when the current hardening task cites the audit; do not read the full audit and all task files every round

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


## Standard development environment

CartCare officially targets **Python 3.12**.

Use `uv` as the canonical local dependency and environment manager.

The dependency source of truth is:

- `pyproject.toml`
- `uv.lock`

`requirements.txt` and `requirements-dev.txt` may remain as compatibility/export entry points for Docker, CI, or pip users, but they are not the canonical dependency definition.

Standard local setup and test commands:

```bash
uv sync --dev
uv run python -m pytest -q
```

Do not add Python 3.14 compatibility work unless a task explicitly requires it.

### Chroma runtime contract

Application code must access Chroma through the external Chroma server using `chromadb-client` / `chromadb.HttpClient`.

Do not reintroduce `chromadb.PersistentClient` or an embedded/local Chroma fallback without an explicit architecture decision.

If the Chroma service is unavailable, fail clearly instead of silently switching storage modes.


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

## Post-T12 evidence-driven hardening (V3)

T01–T12 are completed historical milestones. For Phase-2 tasks, follow `docs/hardening/README.md` and **only the current** `docs/hardening/tasks/<Axx>.md` when present. The older `docs/CartCare-Agent-Hardening-V2.md` is superseded by V3. The 2026-10-11 audit (`docs/engineering/project-audit-20261011.md`) describes evidence at its recorded HEAD and uncommitted workspace; it is not a substitute for checking current code. If the V3 files are missing, report that rather than silently running the V2 backlog.

For A-series tasks:

1. Work on **one `Axx/issue-id` at a time**. Confirm `HEAD`, dirty worktree, executable path, and existing tests. Preserve unrelated changes; stop after reporting results, without automatically starting the next task.
2. The audit's **15 successful isolation probes show observed defects, not completed fixes**. Check relevant evidence, write a regression for **expected safe behavior** (red before repair, green after), and run related tests. If already fixed at current HEAD, prove it and record `verified_no_fix` rather than making unnecessary edits.
3. Follow V3 task priority: in particular, audit-confirmed **N01 idempotency/identity reuse, N03 Provider error disclosure, and N02 authorization/Trace access** are not merely hypothetical. Do not incorrectly promote the separate A01 last-round Tool Use hypothesis to a confirmed defect without its own test. Detailed sequencing and acceptance criteria belong in task files, not here.
4. Keep auth work minimal and deterministic: a local Demo `Principal/AuthContext` adapter is **not production authentication**; reviewer permissions and restricted operations/Trace endpoints matter. Protecting `/eval/run` with authorization does **not** address the separately observed evaluation shared-state risk. Do not claim public-deployment safety without a separate review.
5. Reuse the current Single Support Agent, Provider, Policy/HITL, Tool Contract, RAG, Memory, Eval, and Demo/Trace implementations. For handoff, distinguish text suggesting assistance from a created record. For RAG, fix scoped correctness issues before controlled experiments. Conditional tasks may be deferred with `known_open` (including reproduced Memory N08/N09); do not redo T11 or add MCP/LangGraph by default.
6. Preserve historical T09–T12 reports; record new evidence separately with commit, environment, test dataset, raw observations, metrics, and limitations. Distinguish Fake SDK/unit, live Redis/Chroma, and real-model HTTP E2E. Never present demonstration metrics as production results.
7. Keep documentation proportionate and update **only the existing Workbench/progress JSON** for task state. Include one developer exercise that can be done without Codex; reserve week 6 for independent coding, debugging, and interview preparation.

Track A-series **outcome** (`fixed`, `verified_no_fix`, `implemented`, `experiment_complete`, `partial`, `deferred/known_open`, or `skipped`) separately from Workbench status. Normally recommend `verify`; the user accepts work before `done`.

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

The canonical local test command is:

```bash
uv run python -m pytest -q
```

If tests cannot run, report the exact reason.
Do not claim success from unexecuted tests.

## Trace and observability

Record observable execution events such as:

- request_id
- routing result (only when the active topology actually routes; otherwise N/A)
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

- routing accuracy (only where routing exists; Single-Agent dispatch is N/A)
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
State whether any of the following should be updated:

- `README.md`
- `docs/CartCare-Codex-Workbench.html` / progress JSON
- `wiki/CartCare定位与技术亮点.md`
- `wiki/重点代码.md`

Do not update other Wiki files unless the user explicitly asks for documentation cleanup.

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
