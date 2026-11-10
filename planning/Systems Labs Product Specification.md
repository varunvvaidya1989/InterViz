# Systems Labs: Product Specification

*Version 1.0. Written to be handed to an AI coding agent (Claude Code or Codex). Working product name:  Suggest a coo**l name for the product. *

## 0. How the coding agent should use this document

- Treat this as the source of truth. Where it says MUST, build it. Where it says SHOULD, build it unless it conflicts with a MUST. Where it says LATER, do not build it now, but do not block it architecturally.
- Work in the milestones from section 13, in order. Finish and test each milestone before starting the next. Do not start billing before the content engine works.
- Before writing code for a milestone, write a short plan in `docs/plans/<milestone>.md` listing files to create, data model changes and tests. After the milestone, update `docs/CHANGELOG.md`.
- Prefer boring, well-supported technology. Keep modules small and typed. Every feature needs tests. Every user-facing string must be in a translation file.
- Ask a human only when a decision is marked OPEN in section 14. Otherwise choose the simplest option and record it in `docs/decisions.md`.

## 1. Product vision

A commercial learning product where software engineers and students learn **data structures and algorithms, system design, software engineering practice and the architecture of well-known products** through step-by-step visualizations, deterministic games, architecture drawing, interview practice and source-grounded coaching. The goal is that a learner can understand a concept visually, apply it under interview conditions, and get hired.

Primary learner journey:

**Choose a skill → understand the mechanism → predict an outcome → experiment → sketch a design → defend a decision → review → revisit weaknesses.**

The visual core is **step-by-step algorithm and system animations** (in the style of VisuAlgo): data on screen, the exact line of code being executed highlighted, and a plain-language explanation, all moving together.

### Business model

- Sell **individual labs** and **bundles** (by track, by level, by company-interview theme, or everything).
- Optional subscription for the AI coach and mock interviews (see section 11).
- A free tier MUST exist: the first lab of each track and the full visualizer for a small set of algorithms.

### Three separate concepts (MUST never be conflated)

| Concept | Meaning | Changes when |
| --- | --- | --- |
| Ownership | The learner has access to a lab | A purchase or grant is made or revoked |
| Completion | The learner finished every activity in the lab | Activities are submitted |
| Mastery | The learner demonstrated the skill | Evidence rules in section 3 are met |

A lab has exactly one identity and one progress record regardless of which bundle granted access. Buying a second bundle that contains the same lab MUST NOT duplicate or reset progress.

## 2. Users

1. **Career starters** (students, bootcamp grads): need fundamentals and visual intuition. Need analogies, no jargon.
2. **Switchers by stack** (frontend, backend, mobile, data/ML): know one stack, need system design and DSA. Content SHOULD show analogies from the learner’s chosen background.
3. **Experienced engineers preparing for senior interviews**: need depth, trade-offs, mock interviews and timed practice.
4. **Team admins** (LATER): buy seats and view team progress.

## 3. Learning model

### 3.1 Lab structure

A lab is a short sequence of **activities** (3 to 8). Each activity has a type and a skill tag. Activity types (MUST): `visualize`, `predict`, `tap-flaw`, `order-steps`, `tune`, `choose`, `build-diagram`. LATER: `code-step`, `defend`, `mock-question`.

### 3.2 Mastery rules

- A lab is **completed** when every required activity has at least one submission.
- A lab is **mastered** when the learner has first-attempt correct evidence on at least 70% of scored activities, including at least one `predict` and one design or defend activity where the lab has them.
- Mastery decays: a mastered skill becomes **due for review** after an interval from a spaced-repetition schedule (section 5.6) and returns to mastered after a passed review.
- Wrong answers create **weakness records** keyed by skill tag. These feed the Revisit queue.

### 3.3 Skill graph

Every activity maps to one or more skill tags (for example `hashing.collisions`, `consistency.read-your-writes`). Tags form a prerequisite graph. The product MUST use the graph to recommend the next lab and to explain why.

## 4. Curriculum scope

Content is data, not code (section 10). Launch targets:

### Track A: Data structures and algorithms

- Foundations: complexity, arrays, linked lists, stacks, queues, binary search, sorting (bubble, insertion, merge, quick).
- Core: hash tables, trees and BSTs, heaps, graphs (BFS, DFS), two pointers, sliding window, recursion and backtracking.
- Advanced: dynamic programming (1D and 2D tables), shortest paths (Dijkstra), union-find, tries, topological sort.

### Track B: System design

- Foundations: request lifecycle, DNS and CDNs, load balancing, databases and indexes.
- Core: caching, queues and backpressure, rate limiting, API design, SQL versus NoSQL.
- Advanced: replication and consistency, sharding, CAP and consensus, consistent hashing, observability, failure and recovery.

### Track C: Software engineering

- Testing and CI/CD, version control workflows, design principles (SOLID), design patterns, code review, refactoring, API versioning, security basics.

### Track D: Real product architectures

- Case studies: URL shortener, chat app, video streaming, ride dispatch, news feed, payment system, search autocomplete, file storage. Each is a guided walkthrough: requirements, estimates, high-level design, deep dives, failure modes.

## 5. Features

### 5.1 Algorithm and system visualizer (the visual core) MUST

Every visualization is driven by a precomputed **trace**, which makes it deterministic, testable and scrubbable.

```ts
type Trace = {
  algorithmId: string;
  input: unknown;
  code: { language: string; lines: string[] }[];   // pseudocode plus real languages
  steps: Step[];
};
type Step = {
  codeLine: number;            // index into the active language lines
  note: string;                // plain-language narration for this step
  state: unknown;              // renderer-specific data snapshot
  highlights?: Record<string, string>; // element id -> role (compare, swap, found, current)
  structures?: { name: string; items: string[] }[]; // queue, stack, call stack
  output?: string[];           // results so far
};
```

Requirements:

- Playback controls: play and pause, step forward and back, jump to start, scrubber, speed (at least 3 speeds). Keyboard shortcuts MUST work (arrows, space).
- Three synchronized panels: the visual, the code with the current line highlighted, and the narration. Learner can switch the code language (at least pseudocode, Python, JavaScript, Java; LATER others).
- Renderers: bars and cells (arrays), linked nodes, trees, graphs, tables (for DP), and call stacks. Renderers consume `state`; they contain no algorithm logic.
- Traces are produced by reference implementations that run server-side or at build time and are covered by unit tests (the final state must be correct, step count must be stable).
- Learner inputs: edit the array, choose a target, draw or edit a small graph, choose a start node. Invalid inputs show clear errors.
- **Predict mode** MUST exist: before the next step is revealed, ask the learner what will happen (for example which cell is compared next, which node enters the queue). Correct first-try predictions count as mastery evidence.
- **Compare mode** SHOULD exist: run two algorithms (BFS versus DFS, quick versus merge sort) side by side on the same input with a step counter.
- Visualizations MUST respect reduced-motion settings and be operable without a mouse.

### 5.2 Lab engine MUST

A data-driven player that renders activities from JSON or YAML. Activity types listed in 3.1. Each activity supplies: prompt, diagram or trace reference, correct answer logic, hints (progressive, max 3), explanation, skill tags, and difficulty. The engine records attempts, time, hints used and first-attempt correctness.

### 5.3 System design diagram sandbox SHOULD (milestone 5)

A 2D canvas where the learner drags components (client, load balancer, cache, queue, database, CDN, service, shard) onto a board and connects them. The product then **runs a simulation** against a scenario (for example 10,000 requests per second, one server failure) and shows traffic flowing, queues filling and bottlenecks turning red. A rubric scores the design on requirements met, single points of failure, scalability and cost. The simulation MUST be deterministic from a seed.

### 5.4 Interview practice MUST (basic) / LATER (advanced)

- Each lab ends with an **interview angle**: the real question the lab prepares for, with a model answer outline.
- **Question bank**: DSA problems with hints, system design prompts, behavioral prompts. Filter by company theme, level and skill.
- **Timed mock mode**: a timed session with a prompt, a notes area, and a final self-review checklist. LATER: spoken answers with transcription and rubric feedback.
- A **readiness score** per track derived from mastery and recency. It MUST be explainable (show which skills are weak).

### 5.5 Source-grounded coaching SHOULD (milestone 6)

An AI coach answers questions about the learner’s current lab and mistakes. It MUST be grounded: answers are produced only from the platform’s own lesson content and approved sources, and every explanation cites the lesson section it used. If the sources do not cover a question, the coach says so rather than guessing. The coach MUST NOT give full interview solutions on request during a timed mock. Rate limits and a per-plan monthly quota apply. Conversations are stored and can be deleted by the learner. Prompt injection from user text or imported content MUST be treated as untrusted data.

### 5.6 Progress, review and recommendations MUST

- Dashboard: owned labs, completed, mastered, due for review, weak skills, streak, readiness per track.
- **Revisit queue**: weakness records and decayed mastery produce short review sessions (5 to 10 minutes). Scheduling uses a documented spaced-repetition algorithm (for example SM-2 style intervals) stored per skill.
- **Next best lab** recommendation uses the skill graph and the learner’s background and goal (target company type, target level, interview date).

### 5.7 Catalog, store and entitlements MUST

See section 11. Learners browse by track, level and skill; locked labs show a preview (the first activity) and a clear unlock path.

### 5.8 Learner profile and onboarding MUST

Onboarding asks: background stack (frontend, backend, mobile, data, new to tech), experience level, goal (job search, promotion, learning) and optional interview date. It SHOULD take under 60 seconds and be skippable. Background changes analogies shown in labs.

## 6. UX requirements

- Visual style: modern, calm, high-contrast, generous spacing, with a distinct color per track. Light and dark themes MUST both be supported.
- Responsive: fully usable on phones, tablets and desktop. The visualizer stacks vertically on small screens.
- Every screen has a clear next action. The learner is never more than two taps from continuing where they left off.
- Feedback is immediate and kind: show what was wrong, why, and a hint before the answer. Never shame.
- Accessibility: WCAG 2.2 AA. All interactions keyboard accessible, visible focus, screen-reader labels for diagram nodes and steps, no information conveyed by color alone, support reduced motion.
- Empty, loading and error states are designed for every view.
- Internationalization: all strings externalized. Launch in English; structure for adding languages.

## 7. Technical architecture

### 7.1 Recommended stack (the agent may substitute equivalents with a recorded decision)

- Monorepo with pnpm workspaces and TypeScript everywhere.
- Web app: Next.js (App Router) with React, Tailwind CSS and a component library such as shadcn/ui.
- Visualization: SVG and Canvas rendered by React components; Framer Motion or CSS transitions for animation. No heavy 3D dependency.
- API: Next.js route handlers or a separate Node service (Fastify). Validate all input with Zod.
- Database: PostgreSQL with Prisma or Drizzle migrations. Redis for rate limiting and sessions or queues.
- Auth: email and password, Google and GitHub sign-in, email verification, password reset. Use an established library (Auth.js or similar). Never roll your own crypto.
- Payments: Stripe Checkout, Stripe Billing and webhooks. Support regional pricing and tax through Stripe Tax.
- AI coach: the Anthropic API behind a server-side service with retrieval over the platform’s content (embeddings in pgvector).
- Content: stored in the repository as validated files (section 10), compiled into the database at deploy time.
- Hosting: containerized deployment, one staging and one production environment, infrastructure as code.
- Testing: Vitest for unit tests, Playwright for end-to-end, Storybook for visual components.

### 7.2 Repository layout

```
apps/web            learner web app
apps/admin          internal admin and content tools
packages/viz        renderers and the trace player
packages/algos      reference implementations that produce traces
packages/labs       activity engine and scoring logic
packages/content    lesson files and schema validation
packages/db         schema, migrations, seed
packages/ui         shared components
docs/               plans, decisions, changelog
```

### 7.3 Key design rules

- Scoring and mastery logic live on the server. The client never decides correctness for anything that affects progress or entitlements.
- Traces for visualizations are generated by tested reference code and cached.
- Idempotent webhooks, idempotent submissions (client-generated attempt ids).
- Feature flags for every LATER capability.

## 8. Data model (core tables)

- `users`: id, email, name, background, level, goal, interview\_date, locale, created\_at.
- `labs`: id, slug, track, level, title, summary, version, status.
- `activities`: id, lab\_id, order, type, skill\_tags, payload (JSON), required.
- `skills`: id, name, track; `skill_edges`: prerequisite\_id, skill\_id.
- `bundles`: id, name, price\_ids, rule (static list or rule by tag); `bundle_labs`: bundle\_id, lab\_id.
- `products` and `prices`: map to Stripe ids.
- `purchases`: id, user\_id, source (purchase, grant, subscription, promo), product\_id, status, started\_at, ended\_at.
- `entitlements` (derived, rebuilt from purchases): user\_id, lab\_id, granted\_by, active. A unique key on (user\_id, lab\_id) enforces one access record per lab.
- `attempts`: id, user\_id, activity\_id, answer, correct, first\_attempt, hints\_used, duration\_ms, created\_at.
- `lab_progress`: user\_id, lab\_id, completed\_at, mastered\_at, first\_try\_ratio. One row per user and lab.
- `skill_state`: user\_id, skill\_id, strength, next\_review\_at, last\_result.
- `weaknesses`: user\_id, skill\_id, count, last\_seen\_at.
- `interview_sessions`: id, user\_id, kind, prompt\_id, started\_at, ended\_at, notes, self\_score.
- `coach_threads` and `coach_messages`: with citation references to content ids.
- `audit_log`: actor, action, target, timestamp.

## 9. API surface (REST, versioned under /api/v1)

- Auth: sign up, sign in, sign out, verify email, reset password, OAuth callbacks.
- Catalog: list labs, lab detail, bundles, preview of a locked lab.
- Learning: start lab, get activity, submit attempt, request hint, get lab progress, dashboard, revisit queue, recommendations.
- Visualizer: get trace by algorithm and input; validate custom input.
- Interview: list questions, start session, save notes, finish session.
- Coach: create thread, send message (streamed), list threads, delete thread.
- Billing: create checkout session, customer portal link, webhook endpoint, list purchases.
- Admin: content validate and publish, user lookup, grant or revoke access, refunds view.

All endpoints MUST validate input, return typed errors, enforce authorization, and be rate limited.

## 10. Content authoring format

Labs live in `packages/content/labs/<slug>/lab.yaml` with activity files beside it. A CI check validates every file against a schema and fails the build on: missing skill tags, unreachable prerequisites, activities with no explanation, or answer keys that do not match the reference implementation. Content has versions; learner progress records the lab version completed. Writers MUST be able to preview a lab locally with hot reload.

## 11. Billing and entitlement rules

- A purchase of a lab grants an entitlement to that lab. A purchase of a bundle grants entitlements to every lab currently in the bundle. Bundle contents SHOULD be able to grow, and new labs added to a bundle are granted to existing owners of that bundle.
- Subscription (LATER or milestone 7): unlocks the AI coach quota, mock interviews and optionally all labs while active. When it ends, entitlements granted only by the subscription end. Labs bought outright remain.
- Refunds revoke the entitlements granted solely by the refunded purchase. Progress is retained and restored if access returns.
- Prices, bundles and promotions are configured in the admin app, not in code.
- Webhooks MUST be signature verified and idempotent. A failed webhook MUST not leave a paid user without access: add reconciliation that compares Stripe to the database daily.
- Emails: receipt, welcome, password reset, review reminders (opt-in), dunning for failed payments.

## 12. Non-functional requirements

- Performance: first meaningful paint under 2.5 seconds on a mid-range phone on 4G. Visualization step changes render in under 100 ms. Traces over 2,000 steps MUST stay smooth through windowing.
- Reliability: 99.9% target for the learner app. Graceful degradation if the coach is down.
- Security: OWASP ASVS level 2 as a baseline. Hashed passwords, CSRF protection, secure cookies, strict Content Security Policy, dependency scanning, secrets in a managed store, least-privilege database roles.
- Privacy: collect the minimum. Support data export and account deletion. Cookie consent where required. Comply with GDPR and similar laws. Do not train models on learner data without opt-in.
- Observability: structured logs, error tracking, request tracing, product analytics (activity completion, drop-off, hint use) with a documented event schema.
- Anti-abuse: rate limiting, bot protection on sign-up, limits on account sharing signals.
- Backups: daily database backups with a tested restore.

## 13. Milestones and acceptance criteria

**M1: Foundations.** Monorepo, CI, design system, auth, database, onboarding, empty dashboard. *Accept:* a user can sign up, verify email, set a background and see a dashboard; CI runs tests, lint and type checks.

**M2: Visualizer core.** Trace schema, player, renderers for arrays, graphs and trees, five algorithms (bubble sort, binary search, BFS, DFS, tree inorder) with code highlighting in pseudocode plus two languages, predict mode. *Accept:* each algorithm’s final state is verified by tests; keyboard-only operation works; reduced motion respected.

**M3: Lab engine and content.** Activity types in 3.1, scoring, attempts, completion and mastery, weakness records, content schema and validation, 15 launch labs across the four tracks. *Accept:* a learner can finish a lab, mastery follows the rules in 3.2, and invalid content fails CI.

**M4: Catalog, store and entitlements.** Stripe Checkout, bundles, entitlement derivation, webhooks, refunds, admin grant and revoke. *Accept:* buying two overlapping bundles yields one progress record per lab; a refund removes only the access it granted; webhook replays do not duplicate anything.

**M5: Revisit and recommendations.** Spaced review, revisit queue, skill graph recommendations, readiness score, dashboard. Start the architecture sandbox. *Accept:* a missed activity appears in the queue; completing a review updates the next review date.

**M6: Interview and coach.** Question bank, timed mock mode, interview angles, grounded AI coach with citations and quotas. *Accept:* the coach refuses to answer outside its sources and cites lesson sections; mock mode blocks full solutions.

**M7: Growth and polish.** Subscription tier, referral and promo codes, email lifecycle, SEO landing pages for free visualizations, analytics dashboards, performance and accessibility audits. *Accept:* WCAG 2.2 AA audit passes; Lighthouse performance 90 or higher on key pages.

**M8: Scale content.** Expand to 60 or more labs, compare mode, more languages for code, team seats (LATER).

## 14. Out of scope and open decisions

**Out of scope for v1:** native mobile apps, a code execution sandbox for learner-written code, live instructor sessions, user-generated content marketplace, recruiter or job-board features.

**OPEN (ask the owner before building):**

1. Final product name, domain and pricing per lab and bundle.
2. Currencies and countries at launch, and tax handling.
3. Whether the coach is included in bundles or sold only by subscription.
4. Licensing and attribution rules for any third-party source material used by the coach.
5. Whether company-themed interview bundles may use company names (legal review).

## 15. Definition of done

A feature is done when: it meets the acceptance criteria, has unit and end-to-end tests, passes accessibility checks, has loading, empty and error states, is documented in `docs/`, emits its analytics events, is behind a feature flag if marked LATER, and has been reviewed in a staging environment on a phone and a desktop browser.

## 16. Suggested first prompt for the coding agent

> Read the product specification in full. Do not write code yet. Propose a detailed plan for milestone M1 and the data model changes it needs, list any questions from section 14 that block M1, then wait for approval. After approval, implement M1 with tests, then stop and report.
