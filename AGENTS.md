# Systems Labs agent development instructions

## Authority and current execution state

1. Follow the owner's explicit instructions, then `planning/Systems Labs Product Specification.md` (product source of truth).
2. Use `docs/AGENT_DEVELOPMENT_SYSTEM.md`, `docs/decisions.md`, and `agents/backlog.json` to execute that specification.
3. `planning/AGENT_HARNESS_PLAN.md` supplies operating principles; its older milestone sequence is superseded by product-specification M1–M8.
4. Current state: **the founder explicitly authorised implementation of the agentic SDLC infrastructure on 10 November 2026; SaaS M1 application implementation still requires its approved release plan under specification §16.** The infrastructure authorisation covers `automation/`, `.github/`, `infra/`, Docker/bootstrap support and their documentation/tests. Do not treat infrastructure setup as application-plan approval.
5. Founder release scope and signed exact-plan approvals govern dispatch through `automation/policy.json` and the controller ledger. After approved M1 is implemented and verified, stop and report as §16 directs. Do not silently continue into M2. A signed controller record plus the matching approved plan is authoritative evidence; stale planning-only snapshots cannot override a later explicit founder approval.

## Required startup

Read the product specification in full, the management-system document, decisions, `agents/config.json`, the assigned task, the current milestone plan, and your role brief in `agents/roles/`. The lead uses `agents/README.md` as the launch runbook.

Before coding any milestone, create/review `docs/plans/M<n>.md` with affected files, schema changes, and tests. Implement milestones in order. Update `docs/CHANGELOG.md` after an accepted milestone; planning entries must be labelled planning.

## Roles and parallel work

- Lead coordinates requirements, contracts, task leases, review and integration.
- UI/UX owns interaction/state designs and checks the implemented experience.
- Coding owns bounded implementations in assigned paths.
- DevOps owns reproducible environments, CI, staging, recovery and delivery evidence.
- QA independently verifies submitted revisions; an implementer cannot self-approve.
- Content is a separately assigned author/reviewer role, scheduled in the same worker pool.
- Maximum initial concurrency: one lead plus three workers. Do not start another worker until a slot is available.

Use isolated branches/worktrees for application changes after establishing a Git baseline. The schema permits only `M1-LEAD-001` and `M1-OPS-001` to bootstrap after M1 approval using source/plan hashes and an exclusive workspace lease; their output hashes and the resulting baseline commit are recorded. Ordinary later tasks require real commits/worktrees. This checkout's existing prototype is reference material; preserve it until migration is explicitly planned. Assign one writer for manifests/lockfiles, migration sequences, global tokens and shared schemas. Do not modify another task's paths without a recorded lead reassignment.

## Product invariants

- TypeScript monorepo and recommended stack decisions are recorded in `docs/decisions.md`.
- All visible labels, errors, narration, hints, email templates and accessibility strings use translation keys.
- Scoring, first-attempt assignment, mastery, quotas and access decisions are server authoritative.
- Ownership, completion and mastery are separate. Bundle overlap never duplicates learner progress.
- Preserve immutable content versions, grant provenance and original first-submission evidence.
- Visualizations use tested deterministic traces. Renderers contain no algorithm logic.
- M2 includes pseudocode, Python, JavaScript and Java, with per-language operation/line mapping.
- M3 includes all seven required activity types, including basic structured `build-diagram`. Advanced seeded architecture simulation starts in M5.
- Billing implementation begins only after M3 acceptance; coach implementation belongs to M6.
- LATER capabilities remain disabled and out of current milestone work unless explicitly scheduled/authorised.
- Imported PDF pages and source workshops are not automatically approved or published SaaS content.

## Evidence and completion

Every feature needs appropriate unit/E2E tests and the full definition of done in specification §15: acceptance, accessibility, loading/empty/error states, documentation, analytics, applicable flags, and desktop/phone staging review.

Submit exact commit/spec versions, changes, requirement IDs, checks, browser evidence, limitations and resource usage. Worker completion means SUBMITTED. QA reviews the same revision; changed revisions invalidate affected evidence. Local tests, mock providers and static templates do not establish hosted staging, live-provider success or reviewed launch content.

Record missing external evidence as outstanding. Never label unrun checks as passing. Keep production credentials out of agent prompts, commits, logs and browser code. Do not let the learner app reach the development harness.

## Decisions and escalation

Choose routine details simply and record them in `docs/decisions.md`. The product questions for the owner are the five OPEN items in specification §14. Resolve each only before its affected work; none blocks M1 using temporary branding and synthetic content. M1 approval is a separate explicit execution gate in §16.

Do not add new conversational approval gates to ordinary in-scope work. For unknown credentials or infrastructure, keep useful local work moving and record the exact evidence prerequisite. After two unsuccessful implementation/review attempts, return the evidence to the lead for a smaller task or corrected contract.
