# Systems Labs: specification-derived agent development system

Prepared 10 November 2026. Status: management and planning pack; no new SaaS implementation or autonomous runner is claimed.

## 1. Start here

The owner's product specification is authoritative: [Systems Labs Product Specification](../planning/Systems%20Labs%20Product%20Specification.md). The earlier [harness plan](../planning/AGENT_HARNESS_PLAN.md) contributes coordination principles. Its roadmap and caching/sketchpad/tutor first assignment are replaced by the specification's **M1 → M2 → M3 → M4 → M5 → M6 → M7 → M8**.

The current prototype remains useful evidence and reference code. It does not satisfy the new SaaS milestones: it lacks the required monorepo, production identity/persistence, trace/code/narration visualizer, activity/mastery rules, commercial access model and production operations.

### Management artifacts

| Artifact | Purpose |
|---|---|
| `AGENTS.md` | Repository-wide instructions for every agent |
| `agents/README.md` | Lead startup and dispatch runbook |
| `agents/config.json` | Initial execution policy and gates |
| `agents/requirements.json` | Requirement IDs, specification references, priority and evidence |
| `agents/backlog.json` | Role-owned tasks, dependencies, scope and acceptance criteria |
| `agents/task.schema.json` | Dispatch/handoff contract shape |
| `agents/roles/*.md` | Lead, designer, coder, DevOps, QA and content role briefs |
| `docs/REQUIREMENTS_TRACEABILITY.md` | Human-readable requirement-to-task map |
| `docs/plans/M1.md` | Detailed initial milestone plan, files, data and tests |
| `docs/decisions.md` | Routine choices and interpretation of specification conflicts |
| `docs/design/LEARNING_EXPERIENCE_CONTRACT.md` | Interaction and learning-quality contracts |
| `docs/content/LAUNCH_LABS.md` | Draft 15-lab launch portfolio and content gaps |
| `docs/data/DATA_CONTRACTS.md` | Versioning, attempts, grants, review and ownership invariants |
| `docs/operations/DELIVERY_GATES.md` | CI/staging/production and recovery evidence |
| `docs/operations/GITHUB_ACTIONS_DOCKER.md` | Proposed GitHub Actions coordination and Docker worker/application automation |

All backlog entries begin PLANNED. A source document or planning artifact is not evidence that its feature is implemented.

## 2. Team model

The lead functions as product manager, architect and integration owner. It turns outcomes into testable requirements, assigns small tasks, resolves routine choices, and decides whether independent evidence meets the requirement. It does not waive failed MUST requirements.

The UI/UX agent owns interaction behaviour as well as appearance: learning objective, misconception, user action, state transitions, progressive feedback, keyboard equivalent, mobile layout, translation keys and failure states.

The coding agent implements approved contracts and appropriate verification within assigned paths. It cannot self-certify independent review or rewrite learning rules because implementation is inconvenient.

The DevOps agent owns reproducibility, environments, CI, staging delivery, recovery and operational evidence. Production credentials stay restricted to authorised deployment jobs.

QA independently tests the submitted revision, including source support, first-attempt correctness, access boundaries, failure handling and accessibility. The content role authors/reviews declarative labs and skill mappings. These roles use the same bounded worker pool; six roles do not mean six concurrent processes.

Initial scheduling capacity is **one lead plus three workers**. The lead can run design and infrastructure work in parallel, then schedule implementation when contracts exist and review when implementation is submitted. Broad assignments such as “build the backend” are rejected in favour of observable slices.

## 3. Two separate execution planes

**Development control plane:** role prompts, model/tool adapters, task state, task leases, worktrees, evidence, reviews and deployment requests. It is operated by the development team.

**Learner application:** Next.js web/admin surfaces, validated API routes, deterministic visualizer and activity engine, account data, purchases, diagrams, content and the constrained Anthropic coach.

Do not expose development tools, task stores, source checkouts or worker credentials through learner APIs. Development-model use and student-coach use have separate usage records and limits.

### What the future runner must enforce

This pack defines interfaces and workflow. A persistent runtime adapter/dispatcher is **not yet implemented**. A host agent can use the pack for managed sessions now; it must not claim unattended orchestration simply because JSON manifests exist.

A future runner must implement: schema validation; dependency and milestone gates; worker leases/heartbeats; process/tool and path restrictions; isolated checkouts; durable event/state storage; cost/time limits; artifact capture; exact-revision review; and safe restart/retry. M1 establishes controlled host-managed sessions and durable evidence artifacts. Implementing a complete unattended scheduler/sandbox/model adapter is a separate future infrastructure assignment, not an extra product requirement silently added to M1.

## 4. Authoritative milestone sequence

| Milestone | Product result | Principal agent work | Exit gate |
|---|---|---|---|
| M1 | Monorepo, identity, database, UI foundations, onboarding, empty dashboard | Lead plan; UX tokens/states; DevOps workspace/CI; coder auth/profile; independent QA | Signup → verification → background → dashboard, plus full §15 evidence; stop/report |
| M2 | Deterministic trace visualizer | Lead trace contracts; content/reference logic; coder generators/player/renderers; UX predict flow | Five named algorithms, correct/stable traces, synchronized panels, four code variants, keyboard/reduced motion |
| M3 | Seven-type lab engine and 15 reviewed labs | Server scoring/attempts; basic diagram activity; content authoring/validation; QA mastery | Completion/mastery verified, invalid content rejected, 15 actual authored labs across four tracks |
| M4 | Store, purchases, bundles, entitlements | Catalog/preview UX; grant ledger; Stripe test-mode events; admin/reconciliation | Overlap/refund/replay cases preserve correct access and one progress identity |
| M5 | Review queue, recommendations/readiness, initial seeded sandbox | Scheduler/skill graph; dashboard; drawing revisions; deterministic simulation/rubric | Review changes schedule; recommendations explain why; seeded scenario and recovery evidence |
| M6 | Question bank, timed mock and grounded coach | Approved-source retrieval; server mock guard; coach storage/deletion/quotas; live evaluation | Supported answers cite sections, unsupported questions abstain, mock solutions blocked, quota/deletion/outage checks |
| M7 | Subscriptions/growth and launch-quality audits | Subscription provenance; promos/referrals; emails/consent; SEO/analytics; audits/recovery | WCAG 2.2 AA evidence, Lighthouse ≥90, performance/SLO/restore checks and release readiness |
| M8 | 60+ reviewed labs and compare/expanded code languages | Reuse validated authoring; renderer coverage; compare semantics; scale QA | Published lab count and coverage evidence; team seats stay LATER unless separately authorised |

Each milestone requires a pre-code plan. M1 explicitly requires owner approval before application implementation and a stop/report after implementation (§16). Later milestones require predecessor acceptance and their own plan; do not invent repeated owner approvals unless the agreed execution policy calls for them.

M4 enables and verifies commercial mechanics in test mode. Public paid launch still requires applicable OPEN decisions and production-quality gates; passing checkout tests alone is not a release decision.

## 5. Dispatch and integration protocol

1. Read the assigned requirement, accepted predecessor artifacts, milestone plan and role brief.
2. Lead resolves routine ambiguity through a decision record. Product-scope conflicts go back to the specification.
3. Coordinator checks the active milestone, approval state, dependencies, allowed paths and populated run limits.
4. Acquire a task lease and create an isolated branch/worktree from a recorded base commit. The two approved initial tasks `M1-LEAD-001` and `M1-OPS-001` have an explicit pre-Git bootstrap exception: use source/plan artifact hashes and an exclusive workspace lease until DevOps creates/confirms the reviewed baseline. Their handoffs identify hashed output artifacts; OPS also records the baseline commit it creates. Every subsequent modifying task requires a real base commit and isolated worktree. No baseline is assumed in this checkout.
5. Worker checkpoints changes and captures relevant evidence. Shared contracts/migrations/lockfiles have one designated writer.
6. Worker submits an exact commit plus acceptance-to-evidence mapping, limitations and usage. SUBMITTED is not accepted.
7. Independent reviewer checks that exact revision. Defects refer to requirement IDs, reproduction steps and observed/expected outcomes.
8. Lead integrates accepted revisions, then reruns affected integrated checks and schedules staging review.
9. Record milestone acceptance only when all exit evidence exists. Update changelog and report the delivered behaviour and remaining limitations.

The plan's `allowed_paths` are directory families, not permission for simultaneous writers. Expand queued tasks into non-overlapping file ownership before dispatch. API-contract changes invalidate dependent task evidence and trigger reassessment.

### State and retries

Task states: `PLANNED → READY → RUNNING → SUBMITTED → REVIEWING → ACCEPTED → INTEGRATED → STAGING_VERIFIED`.

Exceptional states: `REWORK`, `NEEDS_INPUT`, `INTERRUPTED`, `CANCELLED`.

Milestones: `PLAN_REVIEW → APPROVED → IMPLEMENTING → QA → STAGING_REVIEW → ACCEPTED`.

Persist the state and event log outside chat. Model calls cannot directly mark themselves ACCEPTED. Two unsuccessful work/review cycles return to the lead for decomposition; transient infrastructure retries also have bounds. A stale task lease must be reconciled before another worker resumes it.

### Required handoff evidence

Task and requirement IDs; source/spec hash; base/submitted commit; changed paths; unit/E2E and relevant performance/accessibility results; desktop/phone screenshots or recordings; analytics/documentation changes; limitations; migrations/configuration; and usage. Evidence is tied to the revision and environment that produced it.

Use fixtures for routine CI and distinguish them from live OAuth, email, payments, hosting and model validation. Missing credentials are execution prerequisites for real evidence, not permission to mark checks passed or to invent new product OPEN questions.

## 6. Learning and data invariants

- Stable lab identity and one learner/lab progress aggregate, plus immutable content-version evidence.
- Completion means submission of every required activity, regardless of correctness.
- Mastery uses correct first accepted submissions divided by scored activities, threshold `ceil(0.70 × scored count)`, plus correct-first predict and qualifying design evidence where present. Hints are recorded; the specification does not disqualify a hinted first submission.
- Wrong answers update skill-keyed weakness evidence. Later retries never rewrite the first answer. Reviews update review status separately from initial evidence.
- Scores and first-attempt/idempotency decisions are transactional and server authoritative. Client flags cannot award progress or access.
- Every activity has skill tags, prompt, explanation, difficulty and ≤3 progressive hints. Content validation checks 3–8 activities per lab and prerequisite/answer-key correctness.
- One trace step drives visuals, code highlighting and narration. Per-language mapping preserves the logical operation when switching code variants.
- Renderers consume snapshots and contain no algorithm logic; trace generation/reference logic remains independently tested.
- Basic `build-diagram` is M3; scenario simulation with seeded traffic, queues and bottlenecks begins in M5.
- The source-workshop inventory is not the launch-lab count. Track A needs original reference implementations/content and editorial validation.
- Access checks precede paid payload and coach-source retrieval. Retain per-source grants so refunds/subscription expiry cannot revoke independently purchased access.

## 7. Routine decisions already recorded

Use the product's recommended TypeScript/pnpm architecture: Next.js App Router and route handlers, PostgreSQL, Drizzle, Zod, Redis for shared limits, and established Better Auth integration for the required identity lifecycle. Use English translation catalogues, Tailwind/shared UI, Vitest, Playwright and Storybook. Exact compatible versions are checked and pinned during M1.

The legacy Python/static prototype remains a reference during migration. Anthropic + approved-content retrieval with pgvector belongs to M6. Do not mistake the legacy BM25 prototype for the target semantic-retrieval implementation.

These are recorded implementation choices under §7.1, not changes to product scope. See `docs/decisions.md` for evidence and nuances.

## 8. Owner decisions and practical prerequisites

The five §14 product decisions remain OPEN: final name/domain/prices; launch countries/currencies/tax; coach packaging; source licensing/attribution; and company-name use. **None blocks M1** with temporary branding, synthetic fixtures, and local/unbranded staging.

Do not set live prices, register a domain, publish affected third-party content, or enable company-themed commercial claims before the corresponding owner decision. Proposed names may be recorded as suggestions, not assumed to be available or approved.

M1 approval under §16 is an explicit execution gate, separate from those five product choices. Run configuration also needs an actual host adapter, model routing and populated resource limits before unattended execution. The current configuration remains planning-only.

## 9. Definition of finished

Apply all of specification §15 to each feature, not only the shorter milestone summary: acceptance; relevant unit/E2E checks; accessibility; loading/empty/error states; documentation; analytics; applicable flags; phone and desktop staging review.

The management pack is complete when IDs/dependencies/roles/paths are consistent and the M1 plan is reviewable. The SaaS application is complete only when its implemented milestones have real acceptance evidence. The current delivery makes no claim that those application milestones have passed.
