# Systems Labs delivery, operations, and verification gates

Status: planning contract only. No infrastructure, production application, CI pipeline, or deployment is created by this document. No existing prototype test result establishes that a SaaS milestone has passed.

Source of truth: [Systems Labs Product Specification](../../planning/Systems%20Labs%20Product%20Specification.md), especially sections 0, 12–16. Coordination rules: [agent harness plan](../../planning/AGENT_HARNESS_PLAN.md). Data invariants: [data contracts](../data/DATA_CONTRACTS.md).

## 1. Milestone order and authority

The product specification's M1–M8 sequence supersedes the older milestone sequence in the harness plan. Complete and test a milestone before starting the next. Billing starts at M4, after the M3 content engine and launch-content gate pass. Hosted Anthropic coaching starts at M6. Team seats remain a flagged later capability.

Before implementing each milestone, write `docs/plans/M<n>.md` with files, dependencies, schema changes, tests, and acceptance evidence. Record routine choices in `docs/decisions.md`. Update `docs/CHANGELOG.md` after completion. The initial M1 plan requires owner approval before implementation, as specified in section 16; this planning document is not that approval.

Agents cannot self-certify a release. Coding submits an exact commit with evidence; independent QA reviews that revision; the lead integrates accepted work; DevOps verifies the integrated staging revision. Any relevant code, content, migration, or configuration change invalidates affected evidence until checked again.

The development harness runs outside the student application. Worker leases, tools, task databases, credentials, logs, and artifact stores are not learner-facing services. Product tutor requests cannot invoke development tools.

## 2. Proposed architecture baseline

Use TypeScript and pnpm workspaces, Next.js with route handlers, PostgreSQL with Drizzle migrations, Zod validation, and Better Auth or an equivalent established authentication integration. Use shared Redis-backed limits for multi-instance consistency and local mail capture for development/CI. Retain the specification's `apps/web`, `apps/admin`, and shared package boundaries; an additional microservice fleet is not an M1 requirement.

Exact runtime, package, authentication-adapter, database, and Redis versions must be checked for compatibility and pinned at M1. This document makes no claim that the proposed libraries already integrate in this checkout.

Use one migration owner and one ordered migration history. Application credentials do not receive migration or database-administration privileges. Keep staging and production independently configured. Introduce background jobs when the owning milestone needs them: durable account-email delivery at M1, content publication/indexing at M3, payment reconciliation at M4, reviews at M5, and coach usage accounting at M6.

The existing HTML/JavaScript and Python/SQLite application is a reference prototype. Its local PDF routes, browser-only progress, development server, and tutor credential state are not production defaults. Useful algorithms, scenarios, and source metadata may be migrated through explicit, tested tasks.

## 3. Environment contract

| Environment | Data and credentials | Purpose and exit evidence |
|---|---|---|
| Local | Synthetic learner data; isolated PostgreSQL/Redis; captured mail; no production credentials | Reproducible setup, migrations/seed, verification/reset links, deterministic tests |
| Task CI | Fresh isolated database/schema and Redis keyspace; synthetic fixtures; no production secrets | Install/build, lint, type checks, unit/integration/E2E results tied to commit |
| Preview | Synthetic data, development OAuth configuration, captured mail; test payments only from M4 | Browser/design review of a task revision; bounded lifetime and teardown |
| Staging | Separate services and secrets; designated test accounts; payment test mode from M4 | Integrated desktop/mobile verification, migrations, operational drills, release-candidate evidence |
| Production | Approved content and live credentials; managed secrets; least-privilege access | Only release-policy-authorised rollout after gates, followed by post-release verification |

Preview and staging must not copy production learner data by default. Account-email and lifecycle tests must not send messages to arbitrary real recipients. A captured-email journey verifies application mechanics; actual email/OAuth/provider readiness is reported separately before that integration is enabled publicly.

## 4. Evidence contract

Every milestone submission includes a manifest under its run's artifact directory with:

- Milestone/task/run IDs, exact commit, base commit, spec revision, package lock checksum, and migration identifiers.
- Application, content, trace/reference-code, rubric, and retrieval-index versions where relevant.
- Requirement-to-test mapping: expected result, observed result, test command, log/artifact path, and pass/fail status.
- Browser evidence on a phone-sized viewport and a desktop, plus keyboard and reduced-motion checks for changed interactions.
- Loading, empty, validation, unauthorised, unavailable-dependency, and retry states relevant to the change.
- Preview/staging URL and environment identity; synthetic test-account identifiers without credentials.
- Known limitations, untested live integrations, fixture usage, migration/rollback implications, and resource usage.
- Independent reviewer, reviewed commit, findings, and resolution evidence.

Do not mark a check passed merely because an agent says it ran. Distinguish `PASS`, `FAIL`, `NOT_RUN`, and `BLOCKED`. Model/payment/OAuth fixtures must be labelled; they never count as live-provider success. Avoid retaining private answers, raw drawings, source passages, credentials, or tokens in artifacts unless deliberately required with a defined retention/access policy.

## 5. M1 — foundations

### Prerequisites and deliverables

- Git baseline, protected integration workflow, task isolation, ownership of shared manifests/migrations, and a documented local setup.
- pnpm workspace, pinned compatible tools, strict TypeScript, reproducible build, lint/type/test commands, and CI from a clean checkout.
- PostgreSQL schema/migrations/seed; auth, profile/onboarding, and empty dashboard contracts; synthetic seed data only.
- Established email/password and Google/GitHub authentication integration, email verification, password reset, session expiry/revocation, and explicit account-linking rules. Do not implement custom password cryptography.
- All public/authenticated endpoints validate inputs, produce typed errors, enforce the caller's permissions, and have shared rate limits appropriate to their operation.
- Translation catalogues for all user-facing strings; light/dark themes; accessible forms and navigation; designed loading/empty/error states.
- Structured request IDs, error reporting, minimal documented analytics events, health/readiness endpoints, and configuration validation.
- Managed-secret and least-privilege conventions; secure-cookie, CSRF, CSP, dependency/secret-scanning, and audit-log foundations.
- Baseline data minimisation, profile export/account deletion, consent/preferences, log redaction, retention categories, and designated ownership of deletion/restore procedures.
- Daily production-backup design and a staging restore exercise using synthetic users. Agree recovery objectives before a paid release; do not claim a recovery target has been demonstrated until measured.

### Required verification

CI checks fresh installation, type/lint/unit/integration/E2E results, migrations from empty and previous supported state, seed idempotency, and translation-key availability. Auth tests cover duplicate registration, malformed inputs, expired/replayed verification and reset links, unverified-user restrictions, wrong passwords, session expiry/sign-out, OAuth rejection/linking conflicts, and safe errors. Test rate-limit behaviour and log redaction.

Authorization tests use at least two users: one cannot read/update the other's profile or reach admin capabilities. Onboarding supports skip, validation, persistence, and return visits. Export/deletion affect the requesting account only; session revocation accompanies deletion. Data that must be retained for an explicit reason is documented rather than silently kept or deleted.

Staging demonstrates signup → captured verification → background selection → dashboard on desktop and phone. Provide keyboard/focus, theme, mobile, and error-state evidence. A database failure changes readiness without exposing connection details; liveness is independent of a transient database failure.

M1 exit: independent review accepts the integrated commit and evidence. There is no Stripe, production-source ingestion, live AI generation, or paid-catalogue dependency. Any public M1 rollout still requires the agreed environment/release policy and valid authentication/email configuration.

## 6. M2 — visualizer core

CI verifies trace schemas, input limits, stable deterministic output, expected final states, and code-line mappings for bubble sort, binary search, BFS, DFS, and inorder traversal. Renderers consume state without implementing algorithm decisions. Tests cover forward/backward steps, reset, seeking, speed, predict-event identity, and invalid inputs.

The global visualizer requirements name pseudocode, Python, JavaScript, and Java, while the M2 summary says pseudocode plus two languages. Prefer delivering all four in M2 or record an explicit milestone interpretation without treating a smaller implementation as fulfilment of the global requirement.

Staging verifies synchronized visual/code/narration panels, keyboard-only operation, screen-reader descriptions, reduced motion, and responsive layout. Establish reproducible measurement for the stated sub-100-ms step-change target and long traces above 2,000 steps. Evidence includes input fixtures, trace/reference versions, browser recordings, and measured results. Only validated visualizers may be exposed as free public content.

## 7. M3 — lab engine and content

CI must validate every lab/activity against the content schema: 3–8 activities, supported types, skill tags, reachable prerequisites, explanations, hint bounds, version references, locale content, and answer keys consistent with reference implementations. Test the skill graph for cycles and invalid dependencies.

Implement all required activity types, including `build-diagram`. M3 needs a basic structured diagram activity; M5's advanced seeded sandbox is a separate increment. Validate server scoring, first-attempt races, hint accounting, idempotent replay, completion, mastery, and weakness events using the data contracts.

Fifteen authored launch labs across all four tracks must pass content and learning review. Existing PDFs, question counts, and 132 source-workshop templates do not satisfy that gate. New DSA content and real-product architecture activities need authored objectives and verified mechanics.

Publication requires approved sources/attribution, immutable content versions, source-to-section mappings, reference/rubric checks, accessible alternatives, and a successful full learner journey. Imported or model-drafted content stays unpublished until reviewed. Never evaluate arbitrary generated JavaScript/HTML as an activity.

Staging demonstrates a full lab, predictions, deliberate mistakes, progressive hints, recovery, completion without mastery, and valid mastery evidence. Evidence includes source/learning review, content manifests, invalid-content CI examples, concurrency tests, and account-isolation checks. M3 passes before any M4 billing implementation begins.

## 8. M4 — catalogue, store, entitlements

Resolve launch-market, currency, price, tax, and payment-account prerequisites before enabling live commerce. Develop against Stripe test mode. Keep products, prices, bundles, promotions, and grants administratively configurable with server-side permissions and audit events.

Tests cover single-lab purchase, two overlapping bundles, an existing owner receiving a newly added bundle lab, grant/revoke, refund with another valid grant remaining, refund with no remaining grant, and retained progress after loss/restoration of access. Checkout return URLs are not proof of payment.

Verify webhook signatures; reject invalid events; persist unique receipts; handle duplicate delivery, retries, out-of-order events, and processing crashes. Daily reconciliation repairs paid-but-ungranted access and identifies mismatches. Test recovery by intentionally failing processing and then reconciling.

Staging demonstrates purchase → server-derived access → learning, plus refund/replay/reconciliation cases. Confirm locked previews cannot fetch paid activities, answer keys, private diagrams, or coach evidence through alternate endpoints. Evidence includes test-mode transaction/event IDs, grant-ledger derivations, access matrix, reconciliation reports, admin-role tests, and backup/restore/rollback results. Production commerce requires the owner decisions and release policy; test-mode success alone is insufficient.

## 9. M5 — review, recommendations, architecture sandbox

Document and version the spaced-review policy. Test missed-activity weakness creation, scheduling/time boundaries, passed/failed reviews, due-state transitions, and preservation of original first-attempt evidence. Recommendations must follow the skill graph and explain their prerequisites; readiness derives from demonstrated evidence and recency, not purchases or clicks.

Begin the advanced architecture sandbox: validated component/connection schemas, deterministic seeded simulation, versioned rubric, multiple acceptable designs, private drawing ownership, revisions, autosave/retry/draft recovery, and accessible component editing. Test save conflicts, cross-user access, malformed/oversized imports, reload/export, and the separation of semantic graph from drawing appearance.

Staging evidence includes a 5–10 minute revisit journey, scheduling results, recommendation explanation, sandbox replay fixtures, diagram-save/recovery checks, and keyboard/mobile use. Treat uncertain interpretation of freehand marks as a clarification need, not authoritative scoring.

## 10. M6 — interview and source-grounded coach

Anthropic remains the hosted provider. Validate and pin its integration/model configuration at this milestone; the prototype's rejected credential cannot establish readiness. Production explanations retrieve only published lesson sections and approved sources within the user's access and active lab/session scope.

Reserve per-plan monthly quota atomically before a provider request. Enforce request idempotency, context/output/concurrency/time limits, and defined cancellation/failure handling. Track actual provider usage separately from quota reservations; cached/replayed results must not cause a second charge or duplicate grant of allowance.

Mock protection is server-side. Derive active mock state from the authenticated interview session, restrict evidence/reveal endpoints, and block full solutions even when the caller changes client flags, threads, wording, or direct API routes. A system prompt alone is insufficient. Keep permissible hints distinct from full model answers.

CI uses labelled model fixtures and fixed grounding/citation sets. Tests include unsupported questions, forbidden sources, malicious imported/user instructions, citation validity, concurrent quota exhaustion, request replay, provider outage, partial streams, and conversation deletion/export/ownership. Do not log private message bodies by default.

Staging separately demonstrates a valid live-provider response, supported citations, source abstention, mock restriction, quota handling, and graceful model failure while deterministic learning remains usable. Store/delete conversations as the specification requires; the old memory-only prototype policy is superseded. Resolve coach inclusion/subscription policy and source-use permissions before enabling the corresponding feature.

## 11. M7 — growth, subscriptions, polish

Test subscription lifecycle, failed payments, renewal/cancellation, proration policy where offered, and access expiry. An expired subscription revokes only its grants; outright purchases and other active grants remain. Promotions/referrals require replay/abuse checks and an auditable award rule.

Lifecycle emails respect consent and unsubscribe rules. Dashboard analytics use a documented minimal event schema. Public SEO pages expose only approved free/preview content.

Obtain integrated WCAG 2.2 AA audit evidence and Lighthouse performance at least 90 on agreed key pages, using recorded device/network/build conditions. Recheck the specification's phone/4G loading and visualization targets. Report measured results; do not infer compliance from automated scans alone.

Before wider release, run alerting, restoration, and rollback drills across learner data, content/index versions, and private assets. Record the 99.9% availability target and how it is measured; no prelaunch check can establish historical availability. Evidence includes subscription/access cases, email-consent tests, audit reports, operational drills, and the exact release manifest.

## 12. M8 — content scale

Publish 60 or more individually validated labs; generated drafts and PDF topics do not count. Run all content schemas, source/educational checks, simulation/rubric fixtures, and impacted retrieval evaluations. Version compare-mode alignment semantics and test both algorithms on identical inputs without implying their steps have identical meaning.

Expand code languages with validated line mappings and accessible explanations. Load/capacity tests use representative content, trace lengths, and diagrams. Team seats stay off until account/seat administration and organization isolation are explicitly implemented and tested.

Staging evidence includes the published content manifest, regression reports, representative learner-transfer tasks, compare-mode browser journeys, capacity measurements, and content/index rollback compatibility. Use error and learning-quality measurements to prioritise further expansion.

## 13. Common production release gate

Production eligibility requires the milestone's integrated staging acceptance plus:

1. Identifiable immutable application and content artifacts; reviewed configuration and migrations.
2. No unresolved release-blocking findings; precise documentation of limitations and live-provider checks.
3. Server authorization and relevant purchase/source/drawing boundaries exercised against the release revision.
4. Backward-compatible migration/rollback plan. A binary rollback cannot undo incompatible data changes by itself.
5. Daily database backups, required private-asset retention, and a demonstrated restore covering the affected data.
6. Health checks, structured metrics/errors, alert destinations, ownership, and recovery procedures.
7. Release-policy-authorised deployment credentials, post-release smoke checks, and a rollback decision/owner.

Collect aggregate lab failures, save failures, API latency/errors, authentication errors, ingestion lag, payment/entitlement mismatches, retrieval regressions, and model availability/usage as their milestones arrive. Agent-run throughput, review defects, tool failures, and development-model spending belong to a separate harness telemetry stream. Agree retention and access for both streams.

## 14. Owner decisions and milestone blockers

The specification's section 14 is the owner-decision list. No item inherently blocks M1 when it uses a provisional working name, synthetic seeds, and local/unbranded staging.

| OPEN decision | Earliest affected gate |
|---|---|
| Final name/domain/prices | Final public branding/domain setup; M4 catalogue and live commerce |
| Countries/currencies/tax | M4 live commerce |
| Coach bundled or subscription-only | M6 allowance/product policy; M7 subscriptions |
| Third-party source licensing/attribution | M3 publication of affected lessons; M6 source use |
| Company-name usage | Company-themed bundles, marketing, and question categorisation |

Do not substitute an unapproved commercial/legal policy for an owner answer. Work unrelated to that decision can continue within its milestone and existing authorization. Routine architecture choices use the simplest compatible option and a recorded decision.
