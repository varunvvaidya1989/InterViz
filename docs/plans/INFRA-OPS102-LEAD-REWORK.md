# Bounded lead rework after OPS-102 blocked attempts

12 November 2026. Founder requested continued recovery. M1-OPS-101 is integrated;
OPS-102 used two automated attempts, both rejected before publication because
the worker report was not SUBMITTED. Runs 43019919500 and 43038007903 retained no
failure report, so their exact reasons are unknown. Do not infer a code defect or
reset either spent attempt. Current lease is expired and no PR/head exists.

## Lead reassignment and scope

Under AGENTS.md's two-failure escalation rule, assign a separate bounded manual
lead-rework contract `OPS102-LEAD-v1` against the original approved R-1 plan hash
`cfdb4e26aba485a4e302d0bdddbc91fb140365c7df37d0c7eada49f83bafa45d`.
The original task's coding attempts remain 2/2. One coding writer will implement
only its existing three allowed paths: automation/cli.py,
automation/test_amendment_cli.py and automation/README.md. No third automatic
coding claim is authorized. Two manual implementation/review cycles maximum;
independent QA and actual CI/review must certify the exact submission.

The lead first freezes a harness support commit. Ownership of the three task
paths then transfers to the assigned coding worker in its isolated worktree;
the lead does not concurrently edit those paths. The worker submits, never
self-accepts, its code. Source base is current main5672d924 plus this reviewed
support commit. No M2/application scope, policy changes, schema migrations,
production settings or milestone acceptance.

## Support correction

- Preserve sanitized worker failure reports and append failure audit evidence;
  release only the matching failed worker lease and preserve bounded attempts.
  Diagnostics must never publish failed code as a submission.
- Clarify that trusted signed assignment approval supersedes stale planning-only
  snapshots. Allow explicitly assigned infrastructure source edits; continue to
  forbid live approval/state/policy/credential mutations by models. Require
  SUBMITTED for code handoff and retain all other verdicts as failure evidence.
- Import the exact founder-approved planning artifacts at PR14 revision65397b.
  Their canonical plan hash was independently recomputed from committed policy
  and spec bytes and matches the existing signed approval. These files were
  absent from main, including the proposed OPS-102 executable regression.
  Import does not approve a new plan or mark future proposed tests as passing.
- Add a founder-authenticated hosted adoption action for an exhausted unsubmitted
  task's bounded lead rework. Verify exact approved plan/scope/dependencies, no
  active lease, current same-repository PR/head/base and authorized changed paths.
  Record SUBMITTED with the lead author and fresh evidence epoch, without any
  attempt reset or acceptance. Only one initial lead adoption is permitted;
  later revisions use ordinary current-head review/rework rules.
- Adoption requires explicit founder approval of the concrete submitted revision.
  Fresh independent review/CI and protected founder acceptance still precede merge.

## Verification

Tests cover non-founder/stale plan, scope expansion, active lease, dependencies,
two spent attempts retained, duplicate adoption, immutable history, failed report
capture/lease release and no failed publication. Run full infrastructure tests,
independent exact-revision review and hosted CI. Then adopt and review the concrete
OPS-102 lead submission via signed hosted state; verify next implementation work.
