# Security Policy

This project is an authorization-policy primitive. Incorrect behavior can be security-relevant.

Please do not use public issues to disclose a vulnerability that could cause `DENY` to become `AUTO`, allow approvals to match modified actions, bypass a hard budget, or otherwise expand authority unexpectedly.

When integrating this library, treat policy data and approval creation as privileged operations. Do not let an LLM create or modify standing policy or manufacture human approvals.

Fingerprints bind action content; they are not signatures or proof of human identity. Approval replay protection only covers one live `PolicyEngine` instance. Durable replay protection, budget reservations, policy version binding, and execution idempotency belong to the integrating application. Consume authorization and reserve spend atomically before executing external actions.
