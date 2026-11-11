# Systems Labs decision register

Prepared 10 November 2026. Implementation decisions under product specification §§0/7.1. No final brand, commercial policy, source rights or live prices are approved here.

## ADR-001 — Specification and milestone precedence

Adopt product specification v1.0 as source of truth. Follow M1–M8 and retain the older harness only for role/isolation/evidence/recovery principles. Absorb essential agent-delivery setup into M1; remove the old caching-plus-sketchpad-plus-tutor first assignment. M1 requires plan → owner approval → implementation → tests → stop/report under §16.

## ADR-002 — Production migration and stack

Plan a pnpm/TypeScript monorepo using Next.js App Router/route handlers, React, Tailwind/shared UI, PostgreSQL/Drizzle, Zod, Redis/shared limits, Vitest/Playwright/Storybook. Pin compatible maintained runtime/package versions at M1 implementation. Keep Python/static prototype files as reference until a reviewed migration task moves or retires them. No silent framework rewrite in another task.

## ADR-003 — Established identity integration

Select Better Auth as the §7.1-permitted established-library equivalent, with email/password, email verification/reset and Google/GitHub integration. It documents these capabilities in [email guidance](https://better-auth.com/docs/concepts/email) and [basic usage](https://better-auth.com/docs/basic-usage). Configure session revocation, token expiry/replay behaviour and safe linking explicitly and verify the pinned adapter/API; defaults are not acceptance evidence. Use local email capture for development. Live-provider and staged email delivery remain separate evidence requirements.

Authorisation belongs at every protected application entry point, following the [Next.js authentication guidance](https://nextjs.org/docs/app/guides/authentication). UI visibility and route layout checks alone do not establish access enforcement.

## ADR-004 — Visualizer languages and trace mapping

Satisfy §5.1's stronger language set during M2: pseudocode, Python, JavaScript and Java, despite §13's lower milestone minimum. Extend trace metadata with stable logical operation IDs and per-language highlighted-line mappings. Keep runtime narration resolved from translation keys. A language switch preserves the step and visual state. Do not assume the same numeric code line denotes the same operation in all languages.

## ADR-005 — Drawing scope

M3's required `build-diagram` uses typed nodes/connections with accessible editing and deterministic structural evaluation. M5 adds the seeded architecture scenario simulator and broader rubric. Drawing appearance is not correctness. Store semantic graph and editable scene/revisions separately. Defer editor-library choice to its bounded task; the older Excalidraw suggestion does not override the product's interaction contract.

## ADR-006 — Completion and literal mastery

`visualize` is normally unscored but requires explicit checkpoint/end submission for completion. Every scored launch lab has at least one prediction; design-oriented labs include scored `build-diagram`. Mastery threshold is `ceil(0.70 × scoredActivities)` correct first submissions plus required first-correct predict/design coverage. Hints remain recorded but do not silently disqualify a first answer. Zero-scored content cannot award assessed mastery. Retries and repeated purchases never reset original first evidence.

## ADR-007 — Prediction disclosure and attempts

Server-issued attempts/checkpoints pin content and trace versions. Idempotency-key replay returns the stored outcome; conflicting payload replay is rejected. Transactional assignment prevents two tabs from both becoming the first attempt. A pending scored prediction pauses before disclosure; an explicit reveal records unsuccessful prediction evidence for that checkpoint. Viewing an unscored public visualizer does not itself award mastery. No AI call decides deterministic correctness.

## ADR-008 — Content and progress versioning

Separate stable `labs` from immutable `lab_versions` and versioned activities/rubrics. Preserve one current learner/lab progress aggregate plus version-specific evidence and completion history. A republished lab cannot silently reinterpret previous answers. Review evidence and scheduling remain separate from original mastery evidence.

## ADR-009 — Grants and growing bundles

Use a provenance ledger of source-to-lab grants and a unique learner/lab access aggregate. Active access means at least one eligible live grant. Refund or subscription expiry removes only its source grants. Bundle growth backfills grants for existing owners, as §11 requires. Preserve progress while locked. Do not destructively remove published bundle membership in the initial admin implementation; use retirement/versioning so existing grants remain auditable.

## ADR-010 — Reviewer independence and exact revision

An implementer submits; another assignment verifies. Lead accepts only against mapped evidence. Any changed commit or shared contract invalidates affected review evidence. Local fixture success is never relabelled live-provider or hosted-staging success. Missing infrastructure is recorded as an evidence prerequisite.

## ADR-011 — Internationalisation, accessibility and analytics start early

Create shared English catalogue keys for UI, narration, content, errors, hints, emails and accessibility labels. Code snippets remain language-specific source code; explanatory strings use catalogue keys. Establish light/dark themes, keyboard operation, reduced motion, state summaries and events in M1; M7 audits and hardens them. Do not postpone accessibility or privacy foundations until final polish.

## ADR-012 — Baseline performance evidence

Record a repeatable target-device/network profile during M1. Measure the specification's <2.5-second meaningful-paint target through a documented lab measurement with FCP/LCP supporting metrics rather than claiming an unavailable browser metric. In M2 measure <100-ms step changes, synchronized panels and a >2,000-step trace with windowing. M7 adds the Lighthouse ≥90 gate and full regression audit. Test-profile or metric changes require recorded comparisons.

## ADR-013 — Scope of M1 data

Implement only the identity/session/verification schema, profile/preferences, audit, and operational scaffolding needed for M1. Document future immutable content/grants/attempts/review/drawing models now, then migrate them in their owning milestones. M1 does not contain fake paid labs or live purchase data. Use synthetic fixtures and provisional Systems Labs labels.

## ADR-014 — Coach policy and source publication

The production coach is M6, uses approved lesson sections/sources with scoped retrieval and section citations, and has separately tested live Anthropic access. Conversations are stored/deletable as §5.5 requires, superseding the prototype's memory-only behaviour. Derive timed-mock restrictions on the server and enforce retrieval/reveal restrictions beyond prompt wording. Source licensing approval gates publication/use of affected documents; ingestion alone is not permission.

## ADR-015 — Deferred capabilities

Keep `code-step`, `defend`, `mock-question` activity types, spoken mocks, additional code languages, compare mode and team seats outside early milestones. Compare mode and expanded code languages are scheduled for M8. Team seats remain LATER until explicitly activated. Basic interview-angle data belongs with M3 lab content; the question bank/timed sessions/coach experience is M6. Optional subscription is implemented in M7 after the owner selects packaging.

## ADR-016 — Curriculum coverage and source controls

The 15 M3 labs are the initial reviewed portfolio across four tracks; they are not a claim that every §4 topic is complete. Track all remaining algorithms/concepts/case studies through M8 and keep unimplemented topics visible in coverage reports. Market only delivered content. Keep private source PDFs and runtime agent records out of baseline commits/public artifacts by default; local files remain available for approved processing. Shared translations live in `packages/i18n/` for web, admin, content and email use.

## ADR-017 — GitHub Actions and Docker automation direction

Adopt GitHub Actions as the proposed CI/job/deployment coordination layer and Docker for repeatable worker and application environments. Keep agent dispatch/model adapters separate from ordinary secret-free PR checks and from the learner-facing coach. Preserve M1 approval and M1–M8 order. Workflow/image definitions and an unattended agent adapter are not already implemented. Operational detail is in `docs/operations/GITHUB_ACTIONS_DOCKER.md`.

## OPEN owner register — specification §14 only

| ID | Decision | Earliest affected gate | M1 handling |
|---|---|---|---|
| OPEN-01 | Final name/domain and lab/bundle prices | Final brand/domain release; M4 live commerce | Provisional Systems Labs; no domain registration/prices |
| OPEN-02 | Launch countries/currencies/tax handling | M4 production commerce | No live commerce |
| OPEN-03 | Coach in bundles versus subscription | M6 plan/quota product policy; M7 subscriptions | No coach implementation |
| OPEN-04 | Third-party source licensing/attribution | M3 publication; M6 evidence use | Original interface text and synthetic data only |
| OPEN-05 | Company names in themed bundles | Company-themed publication/marketing | Neutral generic labels |

Name suggestion for later owner review: **TraceForge**. It is a creative suggestion only; domain/trademark availability has not been checked. Do not replace the provisional label without the owner's OPEN-01 decision.

## ADR-018 - Exact candidate workspaces and CI attempt evidence

Independent review must inspect the queued submitted commit in its isolated worker workspace. The default-branch controller supplies imports, reviewer role instructions and the agent image; candidate files remain untrusted and sandboxed. A missing object or mismatched HEAD stops execution before any model call. The authenticated diff remains available as context. GitHub action_required is approval waiting, not executed CI evidence. Preserve existing CI receipt identities to prevent historical replay. Approval-waiting runs do not consume receipts. Previously consumed runs need a fresh CI dispatch; attempt-level migration is deferred until evidence ordering is designed and verified. This infrastructure repair does not alter founder approval or acceptance requirements. See docs/plans/INFRA-PR-51-REVIEW.md for scope and evidence.


## ADR-019 - Founder approval buttons replace operational command comments

On 11 November 2026 the founder requested approval-only operations and selected the founder dashboard. Show plan and release summaries and attach exact identifiers automatically on approval. Use the existing authenticated GitHub account to dispatch a founder-only trusted default-branch workflow, retaining exact plan/policy/source/candidate binding and signed hosted state. The local server cannot grant approval; queued requests remain pending until controller confirmation. Keep legacy comment commands for compatibility, remove them from the required founder journey, prepare candidates automatically after QA, and preserve independent review, task limits, protected-path acceptance and production configuration. This infrastructure change does not approve any SaaS milestone or reset stuck tasks.
