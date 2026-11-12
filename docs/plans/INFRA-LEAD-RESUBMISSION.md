# One bounded lead correction after actual OPS-102 review

12 November 2026. Task requirement GOV-002: authenticated amendment replay must
precede gating a retained handoff against the current plan. Actual hosted review
43168305461 requested changes on the first OPS-102 lead candidate. Preserve that
review, every original worker receipt and both spent coding attempts.

Assign the smaller lead correction contract `OPS102-REPLAY-v1` for one corrective
head of the existing founder-owned lead PR. This is the second and final lead
implementation/review cycle under the original two-round bound. It is not a new
coding claim, counter reset, plan amendment, acceptance or merge authorization.

Support base is trusted main `9f7eda10fe89cbf4e857e37a4d494e54f93cd859` in isolated
branch/worktree `fix/lead-resubmission`, `.sdlc/worktrees/lead-resubmission`.
Lead explicitly assigns one writer to `automation/cli.py`, `automation/control.py`,
`automation/test_lead_rework.py` and this plan. The root's OPS-102 code correction
uses another worktree. No dashboard, policy, schema or production changes.

## Contract

- Reuse the founder-authenticated hosted `adopt-submission` action and its exact
  current approved plan, original normalized contract, complete PR/rename scope,
  same-repository/base/current-head and founder author checks.
- An initial adoption remains unchanged. Resubmission requires the same original
  lead PR/author, an OPEN task with a genuine current-epoch change request, no live
  or overlapping lease, accepted dependencies and unchanged approved scope.
- Permit only one new corrective head under a distinct explicit contract. Preserve
  2/2 attempts and all claimant author identities; atomically create a fresh
  SUBMITTED evidence epoch with a `lead_submission_resubmitted` audit event binding
  old/new heads, contract, author, original attempts and rejection evidence.
- Replay is a read only while the exact new head/contract/epoch is still submitted.
  A later rejection or third head cannot be reopened. New-head scheduling requires
  fresh actual independent review and CI; no old evidence/counter is reset.

## Verification and completion

Fixtures cover the two-head lifecycle, audit/transaction rollback, concurrent
duplicate submission, third-head/contract rejection, identity, PR, plan, scope,
dependencies and leases. Run all infrastructure tests, validation and whitespace
checks. Submit the exact support revision for independent review and hosted CI
before founder acceptance. This support does not implement GOV-002 itself or
silently accept the corrected OPS-102 submission.

## Local submission evidence

All 23 lead-rework/resubmission fixtures passed. Full infrastructure discovery
passed 95 tests; infrastructure contract validation and whitespace checks passed.
Tests use local synthetic ledgers and API fixtures: no hosted adoption, actual
review result, merge, production change or deployment is claimed. Independent QA
and exact-revision hosted CI remain outstanding for this support submission.
