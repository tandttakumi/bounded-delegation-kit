from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from typing import FrozenSet


class Decision(str, Enum):
    """Decision returned by the policy engine."""

    AUTO = "AUTO"
    ASK = "ASK"
    DENY = "DENY"


@dataclass(frozen=True)
class Policy:
    """Human-owned standing authority.

    The model may propose an action, but it does not get to modify this policy.
    """

    routine_limit: Decimal
    monthly_limit: Decimal
    allowed_categories: FrozenSet[str] = field(default_factory=frozenset)
    always_ask_categories: FrozenSet[str] = field(default_factory=frozenset)
    denied_categories: FrozenSet[str] = field(default_factory=frozenset)
    currency: str = "JPY"

    def __post_init__(self) -> None:
        if not self.routine_limit.is_finite() or not self.monthly_limit.is_finite():
            raise ValueError("limits must be finite")
        if self.routine_limit < 0 or self.monthly_limit < 0:
            raise ValueError("limits must be non-negative")
        if self.routine_limit > self.monthly_limit:
            raise ValueError("routine_limit cannot exceed monthly_limit")
        overlap = self.allowed_categories & self.denied_categories
        if overlap:
            raise ValueError(f"categories cannot be both allowed and denied: {sorted(overlap)}")


@dataclass(frozen=True)
class ActionRequest:
    """A concrete action proposed by an agent."""

    action_id: str
    category: str
    amount: Decimal
    currency: str = "JPY"
    safety_critical: bool = False
    description: str = ""

    def __post_init__(self) -> None:
        if not self.action_id.strip():
            raise ValueError("action_id is required")
        if not self.category.strip():
            raise ValueError("category is required")
        if not self.amount.is_finite():
            raise ValueError("amount must be finite")
        if self.amount < 0:
            raise ValueError("amount must be non-negative")

    def fingerprint(self) -> str:
        # Structured encoding prevents field-boundary ambiguity. Decimal string
        # conversion preserves all digits without context-dependent rounding.
        payload = json.dumps(
            [
                self.action_id,
                self.category,
                str(self.amount),
                self.currency,
                "1" if self.safety_critical else "0",
                self.description,
            ],
            ensure_ascii=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Approval:
    """One-time approval bound to an exact action fingerprint.

    An approval can resolve ASK, but can never override a hard DENY.
    """

    action_id: str
    fingerprint: str

    @classmethod
    def for_action(cls, action: ActionRequest) -> "Approval":
        return cls(action_id=action.action_id, fingerprint=action.fingerprint())

    def matches(self, action: ActionRequest) -> bool:
        return self.action_id == action.action_id and self.fingerprint == action.fingerprint()


@dataclass(frozen=True)
class PolicyState:
    """Committed spend already authorized in the current policy period."""

    committed: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not self.committed.is_finite():
            raise ValueError("committed must be finite")
        if self.committed < 0:
            raise ValueError("committed must be non-negative")


@dataclass(frozen=True)
class DecisionResult:
    decision: Decision
    reason: str
    projected_committed: Decimal
    approval_used: bool = False
