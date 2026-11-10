# PR #51 review and CI recovery

Infrastructure repair, 10 November 2026. PR #51 review checked trusted controller
`ba8062a750c83247d0694ac7febe4e0758d4bd85` instead of submitted candidate
`ba349bc24b8da454bc482941991dc003ddace3f2`. This falls within existing infrastructure
authorization and does not approve or implement SaaS M1.

## Scope and ownership

One local writer on `fix/review-candidate-workspace`, isolated worktree
`.sdlc/worktrees/review-candidate-fix`, based on `ba8062a`.
Affected paths: `automation/cli.py`, `automation/providers.py`,
`automation/test_runtime.py`, `.github/workflows/review-integration.yml`,
`.github/AUTOMATION.md`, `automation/README.md`, `docs/decisions.md`, this plan.
No schema, approval policy, release scope or application changes.
Requirement: GOV-003 exact-revision independent verification.
Specification SHA-256 (working-tree bytes):
`97d03707d3cebd29671f0bd46fedc492ac6532064b0a8cdbcb1c29396daffb94`.

## Changes and acceptance

- Fetch and check out the authenticated queued candidate in the isolated worker.
  Verify HEAD before the model starts; missing/mismatched candidates fail closed.
- Controller imports, reviewer role text and Docker image remain trusted inputs.
  Candidate checks run only within the existing read-only worker sandbox, without
  controller GitHub/signing credentials.
- Approval-waiting CI is not executable test evidence. Preserve existing completed-run
  receipts; use a fresh CI dispatch for already consumed runs. Attempt-level receipt
  migration is deferred because historical replay requires ordered evidence.
- Status is SUBMITTED for independent review; local verification is not acceptance.

## Verification and outstanding evidence

- Real Git fixtures cover local/fetched/missing candidate objects, wrong HEAD,
  candidate-only files, trusted reviewer instructions and unchanged controller HEAD.
- CI fixtures cover approval waiting, completed-run replay and legacy receipt
  preservation against reverse-order history.
- Repair branch: `python -m unittest discover -s automation -p 'test_*.py' -v`
  passed all 39 tests; `python -m automation.cli validate --scope infrastructure`
  and `git diff --check` passed. Docker/live review was not run.
- Exact unmodified PR #51 candidate passed all 48 local infrastructure tests.
- Hosted CI run 42833767732 originally reported `action_required`. At recovery
  inspection it passed on attempt 2; fresh dispatch 42833778077 also passed.
  Worker run 42834106725 failed publication because rework produced no changes.
- Hosted review must rerun after independent review and integration of the trusted
  controller repair. Preserve attempt limits: exhausted recovery requires bounded
  lead/controller rework, not editing signed state or fabricating acceptance.
- Protected-path acceptance remains required. This repair is pushed as PR #52; hosted CI on its initial revision passed.
  Independent review requested correction of attempt-receipt replay; that change
  is removed in the revised patch. No merge, deployment or release performed.
  Resources: lead plus independent QA; local fixtures and hosted CI.

## Rollback

Revert the repair commit. No schema/data migration is involved; this patch does not
rewrite signed controller state or historical CI receipts.
