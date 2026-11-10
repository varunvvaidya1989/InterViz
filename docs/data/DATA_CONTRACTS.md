# Systems Labs data contracts and invariants

Status: proposed contracts, not implemented migrations. This document expands the core-table sketch in the [product specification](../../planning/Systems%20Labs%20Product%20Specification.md) so coding tasks can preserve its learning, access, and recovery rules. [Delivery gates](../operations/DELIVERY_GATES.md) define the corresponding verification evidence.

Use PostgreSQL with Drizzle migrations and Zod API/content validation under the proposed TypeScript/pnpm application. Exact package/runtime versions, adapters, transaction boundaries, and database constraints must be verified and pinned in M1. One task owns the shared schema/migration sequence at a time.

## 1. Core identity and authorization

- Server-authenticated identity is authoritative. A request body cannot choose another user, admin role, correctness result, entitlement, quota balance, or mastery state.
- Use established auth-library tables/contracts for accounts, sessions, verification, and reset mechanisms. Do not maintain a second independent password/session model in application code.
- Application `users`/profile fields include stable internal ID, locale, background, level, goal, optional interview date, and lifecycle state. Prefer role memberships/permissions over a client-modifiable role field.
- Use UTC instants for events and scheduling. Record the policy/time-zone inputs required to reproduce displayed review dates and quota periods.
- Ownership predicates are required for attempts, progress, drawings, sessions, coach threads/messages, exports, and deletion jobs.
- Record stable public IDs separately from provider IDs. External identifiers have provider/account-scoped uniqueness, not assumed global uniqueness.

An empty dashboard in M1 reads only the authenticated user's profile and supported placeholder state. It does not fabricate purchases, mastery, or readiness.

## 2. Immutable content and stable lab identity

The specification's one-lab/one-progress rule requires stable identity plus immutable versions:

| Record | Contract |
|---|---|
| `labs` | Stable ID/slug and catalogue metadata; draft/published/retired lifecycle. An identity survives revisions and bundle membership changes. |
| `lab_versions` | Unique `(lab_id, version)`; content schema version, manifest checksum, publication state/time, locale/content references, reference-code and rubric versions. A published version is immutable. |
| `activity_versions` | ID tied to one lab version; stable logical activity key; ordering/type/required/scored flags; payload, skill-tag references, hints, explanation, answer-validator reference. |
| `lesson_sections` | Immutable section IDs tied to content version and locale; source links and approved text used by the learner and coach. |
| `content_publications` | Exact manifest/artifact, approver/review evidence, activation and retirement events, rollback target. |

`labs.version` alone is insufficient because changing activities in place would change what past attempts mean. Do not point past submissions to mutable answer keys or rubrics.

The server pins a content version when a learner starts a lab. Define and test the compatibility policy when a newer version appears: retaining an existing version, deliberately moving to a new version, or requiring new activities must be explicit and traceable. A client cannot select a version to erase an earlier first attempt or manufacture new mastery evidence.

`lab_progress` remains unique on `(user_id, lab_id)` as an aggregate. Add per-version progress/evidence records and fields/references for completed/mastered versions. A lab update never silently resets aggregate progress, regrades historic attempts, or claims completion of newly introduced activities.

Answer keys and private validators are server/content-build inputs. A locked preview returns only approved preview payloads. Importing PDFs into an index does not publish them or grant a user access to them.

## 3. Sources and publication approval

Introduce `source_documents`, `source_versions`, `source_sections`, `source_approvals`, and lesson/source mappings when content publication arrives at M3. Preserve document title, original location/page, checksum/version, attribution, approval scope, and publisher/reviewer evidence.

Approval applies to a source version and intended usage. Draft, unapproved, retired, or out-of-scope content must not leak through static files, public APIs, search, citations, or coach retrieval. The current PDF prototype is not an automatic approved-content store.

Index entries reference immutable lesson/source section IDs and publication/index versions. Keep index-activation manifests so a release can restore a prior compatible index. A citation resolves to the exact supplied section/version and its permitted source, rather than merely to the current document name.

Source-workshop counts and detected question counts are inventory metadata, not proof of authored labs, correctness, licensing, or adequate curriculum coverage. Model-generated drafts remain unpublished until reviewed.

## 4. Lab runs, submissions, and idempotency

Suggested records:

- `lab_runs`: user, lab identity, pinned version, start/end state and timestamps.
- `attempts`: stable attempt ID, user, lab run, immutable activity version, submitted answer/reference, server correctness/score result, first-attempt designation, hint evidence, validated timing, validator/rubric version, creation timestamp.
- `submission_requests`: unique `(user_id, idempotency_key)`, payload hash, target activity/run, processing state, result/attempt reference.
- `activity_evidence`: unique `(user_id, activity_version_id, evidence_scope)` or equivalent first-submission lock/aggregate. Keep initial learning separate from review evidence.
- `hint_events`: user/run/activity, hint ordinal, server issuance time; no more than three progressive hints per activity definition.

### Submission transaction

1. Authenticate the user; validate input and activity/run/version compatibility; verify access.
2. Claim or load the idempotency record. An identical replay returns the original outcome. Reusing the key for a different payload/target returns a typed conflict.
3. Atomically claim the activity's initial first-submission position using a database constraint/lock or equivalent transaction-safe operation.
4. Run the appropriate trusted validator against the immutable content/reference/rubric version.
5. Persist the attempt and required evidence events; update completion/mastery/weakness aggregates consistently; complete the idempotency result.
6. Return the stored authoritative outcome.

Two concurrent requests with distinct IDs must not both become the first attempt. A network retry must not create a new mistake, success, weakness increment, or completion event. A crash/retry must not leave an indefinitely claimed request without a defined recovery path.

Do not trust client `correct`, `first_attempt`, `hints_used`, or elapsed time. Client duration can be telemetry; scoring/timing rules require server/session evidence and a documented tolerance. The specification records hint use but does not say hints automatically invalidate first-attempt correctness; do not invent that policy silently.

Required tests include same-key replay, same-key/different-payload conflict, distinct-key concurrency, rollback/crash recovery, stale content/run version, cross-user attempts, revoked access, invalid answers, duplicate hints, and aggregate/event consistency.

## 5. Ownership, completion, mastery, and review

These are four distinct data concerns:

| Concern | Authority and invariant |
|---|---|
| Ownership/access | Active server-derived grants; no implication about learning performance. |
| Completion | Every required activity in the pinned lab version has a submission. Wrong submissions can satisfy participation while not establishing mastery. |
| Initial mastery evidence | At least 70% first-attempt correct among the version's scored activities; include a correct `predict` and a correct design/defend activity where those are present. |
| Review/current strength | Versioned scheduling and review evidence indicate recency/weakness and whether a skill is due. Passing review does not rewrite initial attempts. |

Store the mastery denominator and evaluation policy/version with the evidence result. Unsubmitted scored activities do not disappear from the denominator. Unscored `visualize` submissions must not inflate the ratio. Zero scored activities cannot produce mastery automatically. For integer comparisons use an exact threshold equivalent to `correct_first / scored_total >= 0.70`.

Design scoring uses a versioned semantic rubric accepting the permitted design space; it must not require a reference diagram's exact positions or visual neatness. A self-review checkbox is participation evidence, not authoritative correctness. Source templates from the existing prototype must not be relabelled as mastered activities.

Suggested records are `mastery_evaluations`, `skill_evidence`, `weakness_events`, `skill_state`, `review_sessions`, `review_attempts`, and `review_schedule_events`. Aggregates such as weakness counts and readiness must be reproducible from their authoritative events/versioned policies.

Use a documented, versioned spaced-repetition policy. Store due time, interval, last result, and any policy-specific state required to reproduce the next date. `mastered_at` is historical evidence; a separate due/current-strength status represents decay. A passed review can restore current status without changing original `first_try_ratio`.

Readiness combines evidence and recency and explains contributing weak skills. Purchases, logins, elapsed video time, repeated easy answers, and streaks do not certify mastery. Define account/date boundaries for streaks separately from evidence scheduling.

## 6. Purchase and grant provenance

The unique `(user_id, lab_id)` access aggregate is useful, but its single `granted_by` field cannot represent overlapping grants. Use a ledger:

| Record | Contract |
|---|---|
| `purchases` | User, product/provider IDs, immutable transaction provenance, status, start/end/refund state. Admin grants/promotions/subscriptions have distinguishable source records. |
| `access_grants` | User, lab ID, source kind/source ID, activation/expiry/revocation, reason and audit reference. Uniqueness prevents duplicate grants from the same source. |
| `entitlements` | Unique user/lab aggregate, active iff at least one applicable grant remains active. Rebuildable from the ledger. |
| `bundle_membership_events` | Versioned additions/removals and the purchased/update-policy context needed to determine the affected grants. |
| `webhook_receipts` | Provider/account/event uniqueness, verified event type/identity, processing state, retries and outcome references. |
| `reconciliation_runs` | Comparison period/provider account, discrepancies, repairs, failures, and audit evidence. |

### Grant rules

- A direct purchase grants its lab; a bundle grants its current member labs. Existing bundle owners receive future additions as the specification requires.
- Two bundles containing one lab produce multiple provenance grants and one access/progress aggregate. They never duplicate progress.
- Refunding a purchase revokes only grants attributable to that purchase. Another direct purchase, bundle, promotion, free grant, or active subscription can preserve access.
- When subscription access ends, only that subscription's grants end. Outright purchases remain.
- Loss of access retains progress and attempt history according to the documented data-retention policy; restored access recovers that progress.
- Designate first-per-track free labs explicitly in published content, rather than changing access accidentally through catalogue sorting.

For bundle removals, record the published policy. The simplest compatible default is to preserve already granted purchased labs while adding new ones; do not silently invent a retroactive revocation policy. This does not override a future owner-approved commercial policy.

Webhook event IDs provide deduplication but do not resolve out-of-order state transitions alone. Processing must reconcile provider transaction/subscription state and apply grant changes transactionally. A browser checkout redirect cannot activate a grant. Daily reconciliation repairs discrepancies without duplicating purchases, grants, or progress.

Subscription pricing/allowance and launch-market/tax decisions remain the specification's owner decisions. Build billing only at M4 after the content engine, and subscription behaviour at M7.

## 7. Diagram scenes, semantic graphs, and revisions

Introduce a basic structured `build-diagram` answer at M3. Extend persistence and simulation at M5 rather than deferring the entire required activity type.

Suggested records:

- `drawings`: stable ID, owner, lab/run context, current revision reference, lifecycle/access state.
- `drawing_revisions`: immutable revision ID, drawing ID, parent revision, scene schema/editor version, semantic graph schema version, validated scene/graph or private-object references, assumptions, creator/time and checksums.
- `drawing_saves`: user-scoped idempotency key, expected/base revision, payload hash, and stored outcome.
- `design_assessments`: drawing revision, scenario/seed, simulator and rubric versions, requirements, derived results, explanation/evidence and timestamps.

Keep appearance separate from meaning. Scene data stores shapes, positions, labels, and styles. The semantic graph stores typed components, directed connections, responsibilities, and assumptions. A scene revision and graph revision must be associated consistently before assessment.

Use optimistic concurrency: saves carry the expected base revision; stale writes produce a typed conflict and preserve both the server version and local draft for resolution. Replayed saves do not create duplicate revisions. Saving failures must preserve recoverable work. Validate import size, node/edge references, allowed component types, and export serialization.

Access checks apply to drawing list/read/save/delete/export and private-object download URLs. Never infer ownership from an opaque drawing ID. Arbitrary freehand shapes need learner-confirmed interpretation before semantic scoring. Record the versioned scenario/seed so an assessment can be replayed.

## 8. Coach, interview state, and usage

At M6 introduce `interview_sessions`, versioned question/prompts, coach threads/messages, citation references, quota periods, quota reservations, provider requests, usage events, and conversation deletion/export records. These replace the prototype's memory-only policy when the production feature is enabled.

The authenticated server session establishes whether a timed mock is active. Store prompt/version, allowed hint policy, start/end/deadline, notes, and session state. Solution guards must apply across coach threads, retrieval, lesson reveal routes, and direct API calls; changing a browser mode cannot end the restriction.

Threads belong to a user and permitted lab/session/content scope. Each model request records the exact content/index versions and permitted evidence identifiers, not unrestricted document access. Citations map to immutable approved sections. Treat user answers and imported documents as untrusted evidence, never tool/system instructions.

Quota accounting must be atomic across concurrent API instances:

1. Derive plan allowance and quota period from server-side entitlement/product policy.
2. Claim an idempotent request and reserve allowance before provider invocation.
3. Enforce context/output, concurrency, timeout, and session-policy limits.
4. Settle actual usage and response state; release/refund reservations under a documented failure/cancellation rule.
5. Replaying a completed request returns its result without another provider call or usage debit.

Keep model-provider usage/spending separate from commercial quota units and development-agent spending. Deleting a conversation removes the learner-visible/private message records and follows the defined export/deletion/retention policy; it must not silently falsify aggregate billing/abuse records. Provider-side retention requirements must be documented before launch rather than implied by local deletion.

## 9. Privacy, audit, and recovery contracts

M1 establishes data categories, purpose, owner, retention, export/deletion behaviour, backup implications, and access restrictions. Introduce policies for profile/auth data first and extend them before adding attempts, payments, diagrams, or conversations.

Audit records capture actor, operation, target identifier, timestamp, and correlation/reason sufficient to explain privileged changes. Avoid raw passwords, reset/session/API tokens, full answers, drawings, or retrieved source bodies in routine logs/audits. Content access logs use IDs and scopes. Product analytics have a versioned minimal event schema and respect the relevant consent/preferences.

Document deletion behaviour for accounts, sessions, profile data, private assets, attempts, conversations, and legally/operationally retained purchase/audit records. Test authorization and cascade/anonymization behaviour. Restore procedures must account for deletion markers/policies so restoring a backup does not silently resurrect deleted accounts or expose their private assets.

## 10. Schema rollout by milestone

| Milestone | Introduce/extend |
|---|---|
| M1 | Auth-library tables/adapters, users/profiles, permission memberships, preferences/consent, minimal audit/events, account export/deletion workflow, durable account-email delivery; Redis namespaces/limit policy |
| M2 | Versioned trace/reference schemas and cache keys, supported algorithm/language metadata; no premature commerce |
| M3 | Stable labs and immutable versions; activity/section versions; skills/edges; lab runs; idempotency/attempt/hint/evidence records; progress/mastery/weakness aggregates/events; content/source approval/publication records; basic structured diagram answers |
| M4 | Products/prices, bundle membership history, purchases, access-grant ledger, entitlement aggregate, verified webhook receipts, reconciliation runs, grant/refund admin audit |
| M5 | Review sessions/attempts/schedule events, readiness/recommendation policy evidence; drawings/revisions/save idempotency; versioned design scenarios/assessments and private exports |
| M6 | Interview prompts/sessions/state; persisted coach threads/messages/citations; scoped retrieval/index manifests; quota periods/reservations/provider request/usage records; conversation export/deletion |
| M7 | Subscription lifecycle and allowance/product policies, referral/promotion awards, lifecycle email preferences/events, analytics aggregates |
| M8 | Additional versioned content/compare/language metadata; organization/seat schemas only if the later team feature is separately authorised and implemented |

Do not create a large unused schema solely because a future feature is mentioned. M1 decisions must preserve stable IDs and migration discipline; later milestones add their required business data under reviewed migrations.

Every migration plan states compatibility with deployed code, backfill behaviour, constraint/index validation, restoration needs, and rollback limitations. Immutable content and assessment versions are retained long enough to explain stored learner evidence. A database rollback must not be assumed equivalent to rolling back an application container.
