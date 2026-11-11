# Corrected review contract: immutable candidate, writable fixtures

11 November 2026. Follow-up within the founder's explicit task-recovery request.
The publication repair is integrated and restored M1-OPS-101, but its new hosted
review could not run 37 of 48 tests because read-only tools had no writable temp
directory. The report was BLOCKED with no findings; the publisher incorrectly
converted that environment failure into a code rejection.

Base: `eb54053f1ce1b3c27ac847ee7e4f2056b5da0a42`. One lead writer owns
`automation/providers.py`, `automation/cli.py`, `automation/control.py`, review
fixture tests/preflight wiring and infrastructure docs. No application, policy,
plan approval, production, implementation-attempt or old review-history changes.

## Corrected contract and recovery

- Mount candidate /workspace read-only at the Docker boundary. Mount only the
  harness .agent-output directory separately at /review for scratch/output.
  Permit test fixtures in /tmp through
  Codex workspace-write; suppress Python bytecode in source. Keep all container,
  credential, resource and post-run byte-scan controls. Never use full access.
- A no-key preflight verifies temporary SQLite fixtures work and candidate writes
  fail before any paid model call. Verify this with the pinned actual image.
- Treat BLOCKED/FAIL/SUBMITTED review reports as unavailable executable evidence,
  not code REQUEST_CHANGES. Keep the required review check unsuccessful and store
  audit evidence; do not fabricate an approval.
- The lead assigns a new explicit review-contract version to this corrected
  environment. Preserve old bounded attempt receipts; enforce the existing
  two-attempt cap for the corrected contract. No third coding attempt is added.
- Reopen only a latest historical BLOCKED report with empty findings, on its
  unchanged exact head under the same approved scope, once per corrected contract.
  Genuine code findings/rejections and active leases cannot be reopened this way.
  Use a fresh evidence epoch and fresh CI/review; preserve all historical rows.
- Automatic reconciliation applies the correction after protected founder
  integration. No command comments, signed-state edits or counter resets.

## Verification

Fixtures cover Docker source immutability/scratch, preflight-before-paid-model,
blocked classification, corrected-contract bounds, stale source and real code
findings, old-history preservation and epoch gates. Run all infrastructure tests,
independent exact-revision QA, hosted CI and an actual no-key Docker sandbox probe.
Only actual successful hosted review establishes resumed acceptance readiness.

Official config reference consulted for workspace-write temporary/writable roots:
https://learn.chatgpt.com/docs/config-file/config-reference

Actual no-key checks using the pinned local agent image succeeded: temporary
SQLite creation plus denied candidate write, and all 48 tests on the exact
unchanged `ba349bc24b8da454bc482941991dc003ddace3f2` candidate inside the corrected
nested sandbox. No paid model or remote state mutation was used for these probes.
The working directory must be /review: a read-only /workspace working directory
prevents bubblewrap from creating its reserved metadata mount scaffolding.
