# Recover unchanged submissions after controller failure

11 November 2026. Founder explicitly requested recovery of the existing stuck
task so approved implementation resumes. Infrastructure-only scope, based on
`07da01a8b259daab3b464eeeedd08b1ff3978a07`, branch
`fix/recover-stalled-submission`, isolated worktree `.sdlc/worktrees/task-recovery`.

## Assigned repair

One lead writer owns `automation/control.py`, `automation/cli.py`, a bounded
artifact retrieval/recovery module and tests, scheduled workflow recovery wiring,
operations documentation and this plan. No application paths, release-plan/policy
changes, attempt-counter resets, schema migrations, production or manual signed
state writes. GOV-003 exact-revision review and durable audit remain required.

Task `R-1:story:M1-OPS-101` has two attempts, an expired second lease and no current
head, with its original PR #51 still open at `ba349bc24b8da454bc482941991dc003ddace3f2`.
Authenticated run 42834106725 retained a SUBMITTED worker result with identical
before/after bytes, zero changed paths and a report that no implementation changes
were necessary. Its publication failed only because empty diffs were rejected.
The original rejection of the first submission came from the previously repaired
review checkout mismatch. This is publication recovery, not a third coding attempt.

## Behavior

- Accept unchanged resubmission only for the exact previously recorded PR/head
  under the same approved plan and task contract, never as a new arbitrary PR.
- Hosted recovery verifies GitHub run/workflow/repository provenance, artifact
  identity, matching task/worker/lease/plan/revision and genuinely unchanged bytes.
  Reject missing/expired/tampered/mismatched evidence and active workers/leases.
- Restore SUBMITTED transactionally. Preserve both attempts, budgets, authors,
  original review/CI rows and immutable audit history. Start a new evidence epoch;
  neither previous CI success nor old review can accept the restored submission.
- Invalidate only scheduling caches for this restored head. Request fresh bounded
  independent exact-head review and fresh CI using the already repaired reviewer.
- Reconciliation automatically discovers this recoverable case; after reviewed
  integration the founder need not type comments, edit hashes or reset state.
- Protected-path acceptance remains required before integration. Recovery itself
  never merges, accepts a task, enables application checks or approves a milestone.

## Verification and completion

Unit/integration fixtures cover exact prior candidate, stale plan/PR, active lease,
exhausted attempt preservation, idempotency, wrong artifact/worker/lease/run,
nonempty/tampered diffs, old evidence ineligibility, transaction rollback and
bounded repeated recovery. Independent QA reviews the exact submitted commit.
Run all infrastructure tests, contract validation and whitespace checks, then
hosted CI. Inspect authenticated hosted recovery/review evidence before claiming
work resumed. Until the reviewed controller reaches main, activation is pending.

Bounds: one lead plus at most three workers, two implementation/review cycles;
no paid model calls during local repair, existing policy bounds on resumed work.

## Local evidence

All 49 infrastructure tests, contract validation and whitespace checks passed.
The new fixtures cover transactional restore, immutable history/attempt retention,
fresh epoch evidence, active/stale/mismatched cases, repeated recovery, rollback,
artifact provenance/digest/expiry and credential-free redirects. A real Git clone
fixture rejects altered handoff bytes before restoring a valid unchanged candidate.

Read-only verification against the actual retained run 42834106725 succeeded:
artifact 13772348634 has the authenticated expected SHA-256, matches the interrupted
worker/lease/approved-plan metadata and its entire byte map matches a clean checkout
of `ba349bc24b8da454bc482941991dc003ddace3f2`. Local inspection of the remote snapshot
was advisory (HMAC not checked locally); authoritative restoration remains inside
the signed hosted controller. No remote state, attempt count, approval, merge or
deployment was changed during this verification. Activation is pending reviewed
integration into trusted main.

Independent review of the first revision found a live-publication interruption
window between SUBMITTED and scheduling-cache cleanup. Both live and archived
unchanged publication now record the durable recovery event in the same ledger
transaction. A real-clone interruption fixture verifies that reconciliation
finishes cache cleanup after a crash while preserving all attempts and history.
