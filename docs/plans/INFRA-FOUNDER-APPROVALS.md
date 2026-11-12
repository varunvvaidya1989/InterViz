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

Recovery integration: merge the independently reviewed task recovery and fixture
sandbox corrections without changing approval semantics. Match dashboard review
history by both exact head and current evidence epoch; preserved old rejections
must not label a newly restored submission as code rework. A regression fixture
covers same-head old-epoch rejection versus a current-epoch rejection.

## Recovery and amendment synchronization

12 November 2026. Lead explicitly reassigned integration to
`fix/founder-approval-sync` in isolated `.sdlc/worktrees/founder-approval-sync`.
Base `4240075eb17bcfb134d3add180ab6a0a299e6013` retains the bounded lead-rework
support and OPS-102 started-plan amendment/current-hash barriers. Merge source is
the existing dashboard PR #54 revision `02301be2bb6a840f527cec1fcc119dc830ae47b5`.
This is local integration, not founder approval or a remote merge.

Resolve controller conflicts by retaining both hosted `adopt-submission` and
dashboard `approve` commands. Candidate preparation and release approval also
use OPS-102's `require_current_plan`; approval cards suppress frozen candidates
behind a stale manifest/ledger approval. Preserve amendment processing and all
worker failure/recovery evidence. No policy/schema or learner application change.

Keep `.github/workflows/infrastructure-ci.yml` byte-identical to the trusted base:
the controller refuses a PR redefining the CI that certifies it. Dashboard Python
fixtures run in separate read-only `.github/workflows/founder-dashboard-ci.yml`.
Existing required infrastructure provenance remains unchanged. Final verification
includes all automation/dashboard unit tests and synthetic browser approval tests;
independent QA must review the resulting exact consolidated revision.

The subsequent OPS-102 correction `aff7c7c4d710554e2c487f41990335ed4425b910`
is also merged: ordinary plan import cannot replace a started release's plan,
and identical import replay preserves the original metadata and live leases.

Consolidated local evidence: 113 automation tests and 13 dashboard/transport tests
passed; infrastructure contract validation, JavaScript syntax and whitespace
checks passed. Synthetic Chrome approval browser checks passed. The existing
dashboard browser checks also passed against this worktree on loopback port 8012
using read-only live GitHub data (36 tasks, no warnings); approval dispatch stayed
disabled because the new workflow was absent from trusted main. Browser output
screenshots are ignored artifacts, not staged application or live approval proof.
No remote writes, merges, production setting changes or deployments were performed.
Final independent QA and hosted exact-revision CI remain outstanding at submission.
