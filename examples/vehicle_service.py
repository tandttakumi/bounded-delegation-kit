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

first = engine.evaluate(brake_job, state)
print(first)  # ASK: above the standing routine limit

approval = Approval.for_action(brake_job)
second = engine.evaluate(brake_job, state, approval=approval)
print(second)  # AUTO, but only for this exact action
