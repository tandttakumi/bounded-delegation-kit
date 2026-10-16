from __future__ import annotations

from decimal import Decimal, localcontext
from threading import Lock

from .models import ActionRequest, Approval, Decision, DecisionResult, Policy, PolicyState


class PolicyEngine:
    """Deterministic policy enforcement for agent-proposed actions.

    Invariants:
    - Models do not get to expand standing authority.
    - A one-time approval is exact-action scoped.
    - One-time approval may resolve ASK, never DENY.
    - Hard monthly budget and explicit deny rules remain hard boundaries.
    """

    def __init__(self, policy: Policy) -> None:
        self.policy = policy
        self._used_approvals: set[str] = set()
        self._approval_lock = Lock()

    def evaluate(
        self,
        action: ActionRequest,
        state: PolicyState | None = None,
        approval: Approval | None = None,
    ) -> DecisionResult:
        state = state or PolicyState()
        # Decimal's default precision may round a sum back below a hard cap.
        with localcontext() as context:
            context.prec = max(
                context.prec,
                max(state.committed.adjusted(), action.amount.adjusted())
                - min(state.committed.as_tuple().exponent, action.amount.as_tuple().exponent)
                + 2,
            )
            projected = state.committed + action.amount

        # Hard boundaries. Exact approval cannot bypass these.
        if action.currency != self.policy.currency:
            return self._deny("currency_mismatch", projected)

        if action.category in self.policy.denied_categories:
            return self._deny("category_denied", projected)

        if self.policy.allowed_categories and action.category not in self.policy.allowed_categories:
            return self._deny("category_not_allowed", projected)

        if projected > self.policy.monthly_limit:
            return self._deny("monthly_limit_exceeded", projected)

        # Human confirmation boundaries.
        ask_reason: str | None = None
        if action.safety_critical:
            ask_reason = "safety_critical"
        elif action.category in self.policy.always_ask_categories:
            ask_reason = "category_requires_approval"
        elif action.amount > self.policy.routine_limit:
            ask_reason = "routine_limit_exceeded"

        if ask_reason is not None:
            if approval is not None and approval.matches(action):
                # Consumption is atomic within this engine instance. Callers
                # need durable storage for replay protection across restarts.
                with self._approval_lock:
                    if approval.fingerprint in self._used_approvals:
                        return DecisionResult(
                            decision=Decision.ASK,
                            reason="approval_already_used",
                            projected_committed=projected,
                        )
                    self._used_approvals.add(approval.fingerprint)
                return DecisionResult(
                    decision=Decision.AUTO,
                    reason=f"approved_once:{ask_reason}",
                    projected_committed=projected,
                    approval_used=True,
                )
            return DecisionResult(
                decision=Decision.ASK,
                reason=ask_reason,
                projected_committed=projected,
            )

        return DecisionResult(
            decision=Decision.AUTO,
            reason="within_standing_authority",
            projected_committed=projected,
        )

    @staticmethod
    def _deny(reason: str, projected: Decimal) -> DecisionResult:
        return DecisionResult(
            decision=Decision.DENY,
            reason=reason,
            projected_committed=projected,
        )
