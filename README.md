# Bounded Delegation Kit

A small, dependency-free policy engine for **human-owned authority boundaries** in agentic systems.

LLMs can propose actions. This library decides whether a proposed action is:

- `AUTO` — inside standing authority;
- `ASK` — allowed only after exact human approval; or
- `DENY` — outside a hard boundary.

The core design rule is simple:

> The model may choose an action, but it may not expand the authority that governs the action.

## Why this exists

Agent systems often collapse two separate questions into one:

1. *What should the agent do?*
2. *Is the agent authorized to do it?*

Those should not be answered by the same model. Bounded Delegation Kit makes authorization deterministic and inspectable.

It is intentionally small so it can sit behind an LLM, MCP tool layer, workflow engine, or ordinary application without owning the orchestration stack.

## Guarantees

- Standing authority is supplied by human-owned `Policy` data.
- Per-action and period budgets are checked against caller-supplied committed spend.
- Category allow/deny rules are deterministic.
- Safety-critical and configured categories can require approval even at low cost.
- Approval is bound to an **exact action fingerprint** and consumed atomically once per `PolicyEngine` instance.
- Changing amount, description, category, currency, or safety flag invalidates that approval.
- Approval can resolve `ASK`; it **cannot override `DENY`**.
- No network calls, model calls, telemetry, or external dependencies.

## Example

```python
from decimal import Decimal
from bounded_delegation import ActionRequest, Approval, Policy, PolicyEngine, PolicyState

policy = Policy(
    routine_limit=Decimal("10000"),
    monthly_limit=Decimal("30000"),
    allowed_categories=frozenset({"vehicle_maintenance"}),
)

engine = PolicyEngine(policy)
state = PolicyState(committed=Decimal("8000"))

brake_job = ActionRequest(
    action_id="svc-002",
    category="vehicle_maintenance",
    amount=Decimal("18000"),
    description="Brake service",
)

print(engine.evaluate(brake_job, state).decision)
# Decision.ASK

approval = Approval.for_action(brake_job)
print(engine.evaluate(brake_job, state, approval=approval).decision)
# Decision.AUTO
```

The approval above does **not** authorize a ¥19,000 version of the action or a different description. It is exact-action scoped.

Evaluating with a matching approval consumes it when the result has `approval_used=True`. A second attempt with that action's approval returns `ASK` with `approval_already_used`. Keep the same engine instance alive and use a unique `action_id` for each operation. Approval creation belongs to authenticated application code after human confirmation; a SHA-256 fingerprint binds content, but does not authenticate who approved it.

## Decision order

Hard boundaries are checked first:

1. Currency mismatch → `DENY`
2. Explicit denied category → `DENY`
3. Category outside allowlist → `DENY`
4. Period budget exceeded → `DENY`

Then confirmation boundaries:

5. Safety-critical action → `ASK`
6. Always-ask category → `ASK`
7. Above routine limit → `ASK`

Otherwise → `AUTO`.

An exact approval can convert steps 5–7 from `ASK` to `AUTO`. It cannot bypass steps 1–4.

## Run the tests

No third-party packages are required for runtime or tests.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## Run the example

```bash
PYTHONPATH=src python examples/vehicle_service.py
```

## Integration pattern

A typical agent stack can keep reasoning and authorization separate:

```text
LLM / agent
    ↓ proposes action
Tool / workflow adapter
    ↓
Bounded Delegation Kit
    ├─ AUTO → execute
    ├─ ASK  → obtain exact human approval → re-evaluate
    └─ DENY → stop
```

This project does not execute purchases, bookings, payments, or other external actions. It only returns policy decisions.

## Scope

This is a reference-quality policy primitive, not a complete identity or payments authorization system. Production deployments should add authentication, durable audit storage, policy versioning, revocation, concurrency controls, and domain-specific risk rules.

Approval replay protection is in memory and is lost on restart; multiple engine instances do not share it. The library does not update committed spend, reserve funds, or execute actions. The integrating application must persist approval consumption and budget reservations atomically with execution when those guarantees are needed across processes or restarts. Policy and approval objects must never come directly from untrusted model output.

## Open-source contribution

Created during the 2026 Amazon Build, Ship, Shape hackathon window as an **additional open-source project** alongside the Steward primary-track submission. It turns the bounded-delegation pattern into a reusable, framework-independent library with exact approvals, per-instance replay protection, and 24 automated tests.

## License

MIT. See [LICENSE](LICENSE).
