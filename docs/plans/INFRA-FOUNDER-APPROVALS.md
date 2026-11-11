# Founder approvals in the dashboard

11 November 2026. Authorized infrastructure task: replace founder command comments
with plan and release approval buttons in the existing local founder dashboard.
Founder selected the dashboard in this session. This is not SaaS M1 implementation
or approval of a particular plan/release.

Base: `07da01a8b259daab3b464eeeedd08b1ff3978a07`. Isolated branch/worktree:
`feat/founder-approval-buttons`, `.sdlc/worktrees/founder-approvals`.
One writer owns `automation/cli.py`, new approval module/tests, `.github/workflows/`,
`founder_dashboard/`, its launcher, CI test integration and operations documentation.
The pre-existing untracked dashboard is copied into the worktree; original user
files and README edits are preserved. No schema migration or policy mutation.

## Interaction and contract

- Show a readable plan or QA-passed frozen release summary and an Approve button.
  No typed release IDs, hashes or command comments. Existing comment commands are
  compatibility paths, not part of the founder's required workflow.
- Browser submits a versioned approval intent to the loopback server. Reject
  cross-origin, missing CSRF, wrong identity and stale displayed approvals.
- Only the configured founder's GitHub identity may dispatch the dedicated trusted
  default-branch approval workflow. It restores/verifies signed state, checks the
  exact displayed plan/candidate against current sources and records approval.
- A queued request is shown as pending, not approved, until controller evidence
  confirms it. Plan approval wakes the existing scheduler. Release approval does
  not override production configuration, CI, independent review, QA or scope gates.
- Prepare a release approval card automatically after exact integrated QA passes.
  Publication may proceed only under existing configured production authority.
- An already approved plan remains approved in the UI even if a task is stuck;
  describe recovery as agent work rather than asking for repeat founder approval.

## Verification

Unit/integration fixtures: founder identity, stale hashes/PR heads, tampered plans,
candidate mismatch and missing QA, dispatch without direct ledger mutation,
idempotency, CSRF/origin/body checks and queued/error/confirmed UI states.
Browser checks: readable approval cards, one-click intent with hidden identifiers,
keyboard use, desktop/phone reflow and failure visibility. Preserve existing tests.
Independent QA reviews the exact submitted commit; implementer cannot self-approve.
Hosted activation and live approval evidence stay outstanding until reviewed code
reaches trusted main. No synthetic tests count as staging/provider/launch evidence.

Numeric bounds: one lead and at most three workers; at most two review attempts;
local fixtures and CI only, no paid model dispatch for this implementation.

## Local evidence

Backend: 51 infrastructure tests (including exact founder/version/publication
approval checks), 12 dashboard/loopback tests, infrastructure contract validation,
JavaScript syntax and whitespace checks. Synthetic Chrome browser coverage includes
plan details, hidden identifiers, keyboard approval, pending/confirmed separation,
stale/network/workflow failure states, founder-only controls and phone reflow.
Screenshots: ignored `artifacts/approval-desktop.png` and `approval-mobile.png`.

Read-only live preview on port 8011 loaded 36 current tasks, the existing approved
plan, and the blocked M1-OPS-101 task. It correctly disabled approval dispatch
because the new workflow is not yet on main. No live approval, task reset,
production enablement or deployment has been performed.
