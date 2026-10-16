# Devpost Open Source Mini Challenge fields

Use these after publishing this folder as a **public** GitHub repository named `bounded-delegation-kit` under GitHub user `tandttakumi`.

## Contribution URL

`https://github.com/tandttakumi/bounded-delegation-kit`

For a brand-new open-source project, the repository itself is the contribution. If you prefer, after the first push you may use the first commit URL as the contribution URL.

## Project repository URL

`https://github.com/tandttakumi/bounded-delegation-kit`

## GitHub username

`tandttakumi`

## Description

During the hackathon window I created Bounded Delegation Kit as a separate open-source project alongside Steward. It is a dependency-free Python policy engine that separates agent reasoning from authority enforcement. An agent can propose an action, but deterministic policy decides AUTO, ASK, or DENY using human-owned category and budget boundaries. Approvals are bound to an exact SHA-256 action fingerprint and consumed atomically once per engine instance, so changing the amount, description, category, currency, or safety flag invalidates the approval, and approvals can never bypass hard DENY rules. Authentication, durable replay protection, and transactional spend tracking are explicitly left to the integrating application. The repository includes executable examples, MIT licensing, and 24 automated tests covering routine limits, monthly hard caps, category controls, safety-critical actions, exact approvals, mutation of approved actions, replay and concurrent reuse, exact decimal comparisons, and currency mismatch. This matters because reusable authority enforcement lets agent developers add autonomy without letting the model expand its own permissions.

## Why this qualifies

- Separate, additional project from the Steward primary-track repository.
- Created during the hackathon submission window.
- Public repository with a visible MIT license.
- Meaningful executable feature, not a documentation-only contribution.
- Automated tests are included.
