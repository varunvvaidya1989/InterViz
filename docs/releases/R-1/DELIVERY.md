# M1 delivery, contracts and founder review — proposed

## Dependency waves and ownership

`plan.json` is the canonical story manifest; ARCHITECTURE.md contains the dependency diagram. All proposed code paths refer to future approved work, not this planning worker's authority.

| Wave | Stories | Exclusive ownership / exit |
| --- | --- | --- |
| 0 | M1-OPS-001 | Explicit infrastructure bootstrap under approved plan; root manifests, shell and nonempty smoke tests; existing Git baseline, no pre-Git exception |
| 1 | M1-OPS-003 | Protected app CI/policy/staging proposal; separate acceptance, actual configured checks, refreshed plan approval after policy changes |
| 2 | M1-LEAD-001 | Resolve contracts, acceptance matrix, leases and predecessor revisions after CLI dispatch prerequisites exist |
| 3 | M1-UX-001 | docs/design/M1 only; implementable UI contract |
| 4 | M1-CODE-001 | Sole DB/schema/server/auth owner |
| 5 | M1-CODE-002 | UI/auth/catalogue; layout lease transferred from scaffold owner |
| 6 | M1-CODE-003 | Learner/profile/onboarding/dashboard; catalogue lease transferred |
| 7 | M1-CODE-004 | Privacy settings/routes; settings and catalogue lease transferred |
| 8 | M1-OPS-002 | Actual staging and recovery after accepted integrated app |
| 9 | M1-QA-001 | Independent exact-candidate verification; read-only report |
| 10 | M1-LEAD-002 | Accepted changelog/report only after full evidence; STOP |

The CLI blocks every non-infrastructure dispatch, even lead/UX, until application checks are configured. OPS-001 and OPS-003 are explicitly authorized infrastructure bootstrap; neither implements product identity features. After any protected policy change, trusted controller must recompute/reapprove the manifest against the resulting policy before dispatch resumes. No stale approval survives a policy change.

M1-OPS-003 is an added prerequisite compared with the older nine-task backlog; M1-CODE-004 explicitly handles §12 minimal account privacy now that accounts exist. The manifest contains eleven stories. No backlog or policy is edited by this planning assignment. Contracts are implementation proposals until accepted plan is imported by trusted controller. Story kind `infrastructure` permits only explicitly authorized protected proposals and does not remove protected acceptance.

Manifest paths are bounded upper limits. Before dispatch, narrow them to the actual files needed, record exclusive shared-surface lease and the accepted dependency revisions. Root manifests/lockfile remain DevOps-owned; other workers request a serialized in-scope amendment rather than editing them. Only CODE-001 owns migrations; future schema changes return to it through a recorded lease transfer. UI tokens have one coding owner; designers write the design contract only. Catalogue ownership passes serially between CODE-002/003/004. QA runs read-only and returns structured evidence; trusted controller/lead records it in the proposed evidence locations. QA never repairs implementation silently. Lead cannot become the independent reviewer of its own patches.

Ordinary tasks use isolated controller-created branches/worktrees at a real resolved commit. No pre-Git bootstrap exception is needed or allowed here. One lead plus at most three workers; current controller ledger mutations serialize, so capacity does not mean distributed simultaneous scheduling. Review occupies a worker slot. Dispatch only dependency-accepted work, using signed controller state rather than stale planning snapshots. No workers are dispatched by this planning submission.

## Dispatch and evidence template

A ready contract includes release/story/run ID, specification/version/hash, approved plan hash, trusted policy version, actual base SHA and dependency submissions/acceptances, exact allowed files, single writer/lease, commands/tools permitted, numeric time/token/allocation bounds, acceptance tests, expected artifacts and independent reviewer execution. No unresolved base, credential or ownership placeholder may be dispatched. All existing task-schema requirements still apply; do not use this plan to bypass a missing dispatch field.

Submit exact commit + changed paths, requirement mapping, checks actually run, commands/results, browser/provider/device evidence, migration/deployment implications, limitations, usage and checkpoint history. A submission is SUBMITTED; independent reviewer/controller determine acceptance and integration. Reviews cite exact head. Rework after two unsuccessful cycles returns evidence to lead for smaller contract/correction. Material scope/story/dependency changes require revised exact-plan approval; no worker changes release scope or controller records.

## Estimates and budgets

First-pass planning allocation is eleven story executions at up to 20 worker-minutes each (220 minutes), with 100,000 token bound and $2 allocation each under current policy. Two attempts allocate up to 440 story-execution minutes and $44 versus $22 first-pass allocation. Independent reviews, QA sessions beyond the bounded story, integration and operator provisioning are additional; these figures are not a programme estimate or a guaranteed completion time. Broad auth/UI/operations stories may need several bounded in-scope checkpoint sessions; lead must decompose before starting if the contract cannot fit the enforced cap. Do not reset attempt counts to evade rework limits.

Estimate 1–3 operator working days after prerequisites for bootstrap/configuration and staging/provider setup, plus implementation/review cycles; external provisioning and founder review can extend elapsed time. Before live dispatch reconcile numeric limits in signed run contract, availability of project spending controls and total service budget. Dollar allocations are reporting targets, not hard pre-spend provider enforcement. Current planning session's measured token/cost totals are unavailable; do not invent them.

## Founder review and acceptance

This submission intentionally does not publish a PR, post comments, push, merge, modify approvals or call GitHub APIs. The trusted controller can publish the planning PR from these artifacts and post the computed approval command after independent planning review. Hashing uses `automation.runtime.plan_document`: canonical JSON of manifest plus current specification digest and canonical policy digest. It is not a plain file hash. `REVIEW.md` records the locally calculated hash and command; the controller must recompute at publication/review. Supporting documents are bound by SHA-256 references in the manifest. Editing them requires updating references and therefore invalidates the plan hash.

Review checklist:

- M1 only, existing prototype preserved, all spec MUST foundation requirements traced.
- UX states, responsive/accessibility/translations, API/schema and ownership contracts implementable.
- Real application CI registration and protected bootstrap precede dependent integration.
- Actual staging/provider/device/recovery prerequisites explicitly identified and no missing result counted as pass.
- Numeric bounds and budget limitations accurately described; independent review and two-attempt rules preserved.
- §16 exact-plan approval still absent; no application code implemented by planning.

Acceptance checklist is in manifest delivery_tasks and AT-01–12. Every feature needs acceptance, unit/E2E tests, accessibility, loading/empty/error states, documentation, events, applicable flags and staging phone/desktop review. M1 exports no LATER capability; flags remain disabled/server-enforced if any placeholders are declared. Missing MUST evidence means incomplete M1, not a waiver. After accepted M1, stop/report; do not automatically start M2. Production release is outside this task and retains separate exact-candidate approval.
