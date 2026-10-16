import unittest
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from bounded_delegation import ActionRequest, Approval, Decision, Policy, PolicyEngine, PolicyState


class PolicyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = Policy(
            routine_limit=Decimal("10000"),
            monthly_limit=Decimal("30000"),
            allowed_categories=frozenset({"vehicle_maintenance", "home_maintenance"}),
            always_ask_categories=frozenset({"home_maintenance"}),
            denied_categories=frozenset({"weapons"}),
        )
        self.engine = PolicyEngine(self.policy)

    def action(self, **overrides):
        base = ActionRequest(
            action_id="a-1",
            category="vehicle_maintenance",
            amount=Decimal("8000"),
            description="Oil service",
        )
        return replace(base, **overrides)

    def test_within_authority_auto(self):
        r = self.engine.evaluate(self.action())
        self.assertEqual(r.decision, Decision.AUTO)
        self.assertEqual(r.reason, "within_standing_authority")

    def test_above_routine_limit_asks(self):
        r = self.engine.evaluate(self.action(amount=Decimal("18000")))
        self.assertEqual(r.decision, Decision.ASK)
        self.assertEqual(r.reason, "routine_limit_exceeded")

    def test_exact_approval_resolves_ask(self):
        a = self.action(amount=Decimal("18000"))
        approval = Approval.for_action(a)
        r = self.engine.evaluate(a, approval=approval)
        self.assertEqual(r.decision, Decision.AUTO)
        self.assertTrue(r.approval_used)

    def test_approval_does_not_cover_modified_amount(self):
        original = self.action(amount=Decimal("18000"))
        approval = Approval.for_action(original)
        changed = replace(original, amount=Decimal("19000"))
        r = self.engine.evaluate(changed, approval=approval)
        self.assertEqual(r.decision, Decision.ASK)
        self.assertFalse(r.approval_used)

    def test_approval_does_not_cover_modified_description(self):
        original = self.action(amount=Decimal("18000"), description="Brake service")
        approval = Approval.for_action(original)
        changed = replace(original, description="Brake + tire service")
        r = self.engine.evaluate(changed, approval=approval)
        self.assertEqual(r.decision, Decision.ASK)

    def test_monthly_limit_is_hard_deny(self):
        state = PolicyState(committed=Decimal("25000"))
        a = self.action(amount=Decimal("8000"))
        r = self.engine.evaluate(a, state)
        self.assertEqual(r.decision, Decision.DENY)
        self.assertEqual(r.reason, "monthly_limit_exceeded")

    def test_approval_cannot_bypass_monthly_limit(self):
        state = PolicyState(committed=Decimal("25000"))
        a = self.action(amount=Decimal("8000"))
        r = self.engine.evaluate(a, state, Approval.for_action(a))
        self.assertEqual(r.decision, Decision.DENY)
        self.assertFalse(r.approval_used)

    def test_denied_category_is_hard_deny(self):
        # Use a policy where weapons is in scope but explicitly denied to exercise the deny branch.
        policy = Policy(
            routine_limit=Decimal("10000"),
            monthly_limit=Decimal("30000"),
            allowed_categories=frozenset(),
            denied_categories=frozenset({"weapons"}),
        )
        engine = PolicyEngine(policy)
        a = self.action(category="weapons")
        r = engine.evaluate(a)
        self.assertEqual(r.decision, Decision.DENY)
        self.assertEqual(r.reason, "category_denied")

    def test_unknown_category_is_denied_when_allowlist_present(self):
        r = self.engine.evaluate(self.action(category="travel"))
        self.assertEqual(r.decision, Decision.DENY)
        self.assertEqual(r.reason, "category_not_allowed")

    def test_always_ask_category(self):
        r = self.engine.evaluate(self.action(category="home_maintenance"))
        self.assertEqual(r.decision, Decision.ASK)
        self.assertEqual(r.reason, "category_requires_approval")

    def test_safety_critical_asks_even_under_routine_limit(self):
        r = self.engine.evaluate(self.action(safety_critical=True))
        self.assertEqual(r.decision, Decision.ASK)
        self.assertEqual(r.reason, "safety_critical")

    def test_exact_approval_can_resolve_safety_critical_ask(self):
        a = self.action(safety_critical=True)
        r = self.engine.evaluate(a, approval=Approval.for_action(a))
        self.assertEqual(r.decision, Decision.AUTO)
        self.assertTrue(r.approval_used)

    def test_currency_mismatch_denied(self):
        r = self.engine.evaluate(self.action(currency="USD"))
        self.assertEqual(r.decision, Decision.DENY)
        self.assertEqual(r.reason, "currency_mismatch")

    def test_projected_committed_is_reported(self):
        state = PolicyState(committed=Decimal("7000"))
        r = self.engine.evaluate(self.action(amount=Decimal("8000")), state)
        self.assertEqual(r.projected_committed, Decimal("15000"))

    def test_negative_action_amount_rejected(self):
        with self.assertRaises(ValueError):
            self.action(amount=Decimal("-1"))

    def test_invalid_policy_limits_rejected(self):
        with self.assertRaises(ValueError):
            Policy(routine_limit=Decimal("20"), monthly_limit=Decimal("10"))

    def test_approval_cannot_be_reused(self):
        action = self.action(amount=Decimal("18000"))
        approval = Approval.for_action(action)
        self.assertTrue(self.engine.evaluate(action, approval=approval).approval_used)
        # Even reconstructing the same approval cannot replay an action.
        result = self.engine.evaluate(action, approval=Approval.for_action(action))
        self.assertEqual(result.decision, Decision.ASK)
        self.assertEqual(result.reason, "approval_already_used")
        self.assertFalse(result.approval_used)

    def test_concurrent_approval_is_consumed_once(self):
        action = self.action(amount=Decimal("18000"))
        approval = Approval.for_action(action)
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(
                lambda _: self.engine.evaluate(action, approval=approval), range(32)
            ))
        self.assertEqual(sum(r.approval_used for r in results), 1)
        self.assertEqual(sum(r.decision == Decision.ASK for r in results), 31)

    def test_denial_does_not_consume_approval(self):
        action = self.action(amount=Decimal("18000"))
        approval = Approval.for_action(action)
        denied = self.engine.evaluate(action, PolicyState(Decimal("20000")), approval)
        self.assertEqual(denied.decision, Decision.DENY)
        self.assertTrue(self.engine.evaluate(action, approval=approval).approval_used)

    def test_fingerprint_distinguishes_field_boundaries(self):
        first = self.action(category="vehicle|100", amount=Decimal("1"))
        second = self.action(category="vehicle", amount=Decimal("100"), currency="1|JPY")
        self.assertFalse(Approval.for_action(first).matches(second))

    def test_fingerprint_keeps_all_amount_digits(self):
        first = self.action(amount=Decimal("18000.00000000000000000000000001"))
        second = replace(first, amount=Decimal("18000.00000000000000000000000002"))
        self.assertFalse(Approval.for_action(first).matches(second))

    def test_approval_binds_every_action_field(self):
        original = self.action(amount=Decimal("18000"))
        for changes in (
            {"action_id": "other"}, {"category": "home_maintenance"},
            {"currency": "USD"}, {"safety_critical": True},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(Approval.for_action(original).matches(replace(original, **changes)))

    def test_non_finite_money_rejected(self):
        for value in ("NaN", "Infinity", "-Infinity"):
            amount = Decimal(value)
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.action(amount=amount)
                with self.assertRaises(ValueError):
                    PolicyState(committed=amount)
                with self.assertRaises(ValueError):
                    replace(self.policy, routine_limit=amount)
                with self.assertRaises(ValueError):
                    replace(self.policy, monthly_limit=amount)

    def test_tiny_excess_cannot_round_under_monthly_cap(self):
        action = self.action(amount=Decimal("0.000000000000000000000000000001"))
        result = self.engine.evaluate(action, PolicyState(Decimal("30000")))
        self.assertEqual(result.decision, Decision.DENY)
        self.assertEqual(result.projected_committed, Decimal("30000.000000000000000000000000000001"))


if __name__ == "__main__":
    unittest.main()
