# Founder-led agent SDLC

Prepared: 10 November 2026. This document specifies the operating contract for the authorised development-automation infrastructure. It does not approve M1 SaaS application implementation, mark a milestone accepted, or establish that GitHub, Docker workers, model providers or deployment environments are connected.

The product source of truth remains `planning/Systems Labs Product Specification.md`. The latest founder instruction authorises building the SDLC infrastructure now; that infrastructure authority is separate from the product specification §16 requirement to obtain approval of the M1 application plan. Milestones M1–M8 remain sequential. No billing or coach work is pulled forward by constructing this harness.

## 1. What the founder does

The founder reviews a concrete release/milestone plan containing stories, UI/UX, architecture and operations. Approval binds that exact plan's hash. Agents implement bounded assignments, an independent agent reviews the code, automated checks run, and QA exercises an integrated candidate. Bugs return to the responsible task within fixed rework limits. The founder then reviews a release packet and approves the exact candidate commit and artifact hashes.

Routine coding, review discussion, local checks and evidence collection do not require repeated conversational permission. Product choices marked OPEN in specification §14 still go to the founder before the affected feature is built. Infrastructure setup values such as repository identity, founder usernames and provider access are prerequisites, not facts agents may invent.

### Current configuration

`automation/policy.json` starts in **dry-run** mode:

- Founder username allowlist is empty. An empty list denies approvals; it is not a wildcard.
- Repository identity is null and connection is unverified.
- Development provider/model selection is pending. Codex and Claude are candidates, not active credentials or approved paid execution.
- Docker daemon, worker image, registry and deployment readiness are unverified.
- Remote controller state uses the planned `sdlc-state` branch and requires `SDLC_STATE_SIGNING_KEY`; it is disabled until configured. Workers never receive that key.
- No live paid model calls, remote worker execution, merges, registry publishing or production deployments are enabled.
- SaaS application checks are not configured until the application workspace exists. Prototype checks remain optional reference evidence.

Dry-run can validate contracts, inspect readiness, prepare plans, exercise local fixture state and run infrastructure checks. A successful dry-run or a successful `doctor` process exit is not evidence that external dependencies are configured.

## 2. Roles and authority

The runtime allowlist is `lead`, `coding`, `ui-ux`, `devops`, `review`, `qa`.

| Role | Responsibility | Authority limit |
|---|---|---|
| Founder | Product decisions, exact-plan approval, exact-release approval, configured access | Identity must be authenticated and present in the configured founder allowlist. |
| Lead | Stories, requirement mapping, architecture decisions, task/dependency graph, integration proposal | Cannot impersonate the founder, self-approve release authority, expand policy from a worker result, or bypass missing evidence. |
| UI/UX | Learner flows, component/states, diagrams, accessibility, responsive design, implementation review | Delivers assigned design artifacts; cannot redefine mastery or authorise unrelated implementation. |
| Coding | Implement assigned paths and submit code/tests/evidence | Cannot accept its own implementation as independently reviewed or change policy to enable merging. |
| DevOps | Reproducible worker/application builds, CI, environments, observability, recovery | Production and control-plane credentials belong to trusted jobs, not general workers. |
| Review | Independent exact-revision code review and bounded discussion with the author | Must use an execution context distinct from the author; an approval is invalid after relevant code changes. |
| QA | Integrated acceptance, regression, security/accessibility/learning checks as applicable | Returns evidence-backed defects; cannot transform fixtures or unrun checks into acceptance. |

Learning/content review can be a bounded lead/review/QA assignment under this initial runtime allowlist. A future additional runtime role requires an explicitly reviewed policy change; a prompt cannot grant itself a new role.

The trusted coordinator validates task schemas, dependency states, limits, allowed paths and evidence. Agent text is a proposal or handoff, never executable policy. GitHub issue bodies, PR text, imported PDF text and learner text are untrusted data. Never interpolate them into shell commands.

## 3. Before the founder approves implementation

The lead assembles a versioned plan packet with at least:

1. **User stories:** learner/admin actors, outcomes, requirement IDs, acceptance scenarios and scope exclusions.
2. **UI/UX:** journeys, screen/component contracts, interactions, phone/desktop behaviour, accessibility, themes, translations and loading/empty/error states.
3. **Architecture:** module/API/data boundaries, schema/migration effects, authentication/authorisation, integration contracts and recorded technical choices.
4. **Operations:** local/CI/Docker setup, environments, secret boundaries, observability, rollout/rollback and recovery evidence expected.
5. **Acceptance tests:** requirement-to-check mapping, independent review/QA assignments, required live versus fixture evidence and definition of done.
6. **Delivery tasks:** dependencies, assigned role/path allowlists, shared-file leases, task budget, expected artifacts and stop conditions.

The plan manifest identifies specification version/hash and the policy hash used for evaluation, and hashes each included artifact. The coordinator computes and displays the manifest SHA-256. The founder approves that exact value through an authenticated control surface. The adapter documents the exact command/button syntax; this document does not claim that a GitHub UI control already exists.

Recorded approval contains authenticated actor, source event/record ID, timestamp, plan ID, specification hash, manifest hash and trusted policy hash. No model-produced `approved: true` field is an approval. Updating a material story, interaction, architecture boundary, operation, task scope or gate invalidates the affected approval and requires an updated packet. Editorial changes should still produce a new hash; the coordinator must never claim that a different byte sequence is the approved artifact.

## 4. Formal flow and evidence gates

The durable ledger records state changes, exact revisions, responsible execution IDs and evidence references. State names in the concrete runner must map to this flow; labels alone cannot satisfy a gate.

| Stage | Entry authority | Required output/evidence | Next transition |
|---|---|---|---|
| Plan drafting | Authorised planning/infrastructure work | Stories, UI/UX, architecture, operations and task packet | Plan ready for founder review |
| Plan approval | Verified founder | Exact current manifest/specification/policy hashes | Dependency-ready implementation assignments |
| Implementation | Approved plan and task/path/budget validation | Exact commit, changed paths, acceptance mapping, tests and limitations | Submitted for independent review |
| Independent code review | Reviewer context distinct from author | Exact-commit findings and resolutions; bounded discussion record | Accepted for CI or returned for rework |
| CI | Accepted reviewed revision | Required checks from trusted configuration; logs/results tied to commit | Candidate integration QA or returned defect |
| Integration QA | Review + CI passed for candidate inputs | Integrated revision, relevant API/browser/accessibility/content evidence, operational results | Release packet ready or returned defect |
| Founder release review | Verified founder | Candidate commit, immutable artifact digest, evidence-manifest hash, trusted policy hash | Exact candidate approved, or held |
| Merge/release | All configured gates, enabled execution policy and least-privilege trusted controller | Exact approved revision/artifact, deployment identity and result | Post-release verification and audit |

Integration QA can use an isolated integration branch or candidate checkout; it is not permission to merge unreviewed code to the protected branch. If merging creates a new revision, verify the resulting tree and rerun affected checks; do not silently label a different merge commit as the approved candidate. Production promotes a tested immutable artifact, not a newly rebuilt unverified variant.

A worker declaring success means **submitted**. Acceptance needs independently verified evidence. Relevant code/content/configuration/migration changes invalidate affected review, CI and QA evidence. Release approval is for one candidate; it is not standing authority for subsequent commits.

## 5. Bounded review, bugs and recovery

Initial limits are two implementation attempts per task and two review rounds, including the first attempt/round. Discussion is bounded to four messages per round. Numeric time/model-token/cost limits must be supplied before live dispatch; null placeholders fail readiness rather than permitting unbounded spend.

A review finding identifies the requirement, exact revision/path, expected result, observed result, severity and verification needed. The author can respond with a change or evidence-based disagreement. The lead resolves a scope or contract disagreement and records its reason; the author cannot mark their own review accepted.

QA bugs return to the responsible task, preserving original IDs, evidence and remaining limits. A bug fix produces a new revision and reruns affected gates. After the configured limits, return the accumulated evidence to the lead for decomposition, correction or founder input when the issue is actually an OPEN product decision. Do not evade limits by repeatedly cloning the same assignment under fresh IDs.

Interrupted work resumes from a known checkpoint/commit after acquiring the task lease. A retry reconciles external state before creating another PR, deployment or other mutation. Missing evidence is `NOT_RUN` or `BLOCKED`; failure is `FAIL`. Neither state may be relabelled `PASS` because retry limits were reached.

## 6. Policy and path protection

Every task has an explicit path allowlist which is narrower than the trusted policy. The initial allowed application roots are the specified future monorepo `apps/`, `packages/`, plus `docs/`, `tests/`, and reference-prototype `rag/` with named root files. These are path permissions, not permission to start unapproved M1 work. Shared manifests, migrations, shared UI and content schemas require a single-writer lease.

Separate infrastructure roots permit an explicitly authorised INFRA assignment to prepare changes to the harness, workflows and worker image. This is permission to submit a protected patch for review, not permission to accept it or load it as trusted controller policy. Such assignments retain the protected-path review/founder gate and cannot enable their own automatic merge.

Normalize separators/case, reject absolute paths and parent traversal, and resolve links before enforcing boundaries. A broad `docs/` permission does not override a protected-file rule.

Protect `automation/`, `.github/`, agent policy/configuration, applicable `AGENTS.md` files, worker infrastructure and the founder SDLC contract. Such changes require independent review and founder approval. They cannot be automatically merged by the same proposed policy that changes its own gates. Evaluate a proposed change under the trusted **base** policy/controller, not a policy loaded from the worker's candidate tree.

Workers cannot broaden their own roles, tools, secrets, required checks, founder allowlist or merge authority. Legitimate policy updates are a separate reviewed infrastructure change. Trusted control-plane writes to signed state are narrowly scoped and do not grant workers write access to control-plane code or signing secrets.

## 7. Checks: infrastructure versus learner application

### Infrastructure checks

The required GitHub status check is **`sdlc-infrastructure-ci`**. Its trusted workflow must cover both:

```text
python -m unittest discover -s automation -p test_*.py -v
python -m automation.cli validate --scope infrastructure
```

The readiness report is separate:

```text
python -m automation.cli doctor --format json
```

`doctor` may successfully print a report showing unconfigured dependencies. Its process exit must not be mistaken for repository/provider/Docker readiness. The report must show which live prerequisites are unmet.

Infrastructure verification covers founder identity rejection, plan/release hash mismatch, independent-author/reviewer separation, review limits, state transitions, path protection, check requirements, provider/merge dry-run restrictions, signed remote-state verification and recovery/idempotency. No declaration in this document claims those tests have run or passed.

### Application checks

The future M1 workspace does not yet provide its configured TypeScript lint/type/unit/integration/E2E/content/migration commands. Keep the application suite explicitly unconfigured and block SaaS dispatch/acceptance until the approved implementation supplies it. An empty required-check list is not a passing application gate.

Existing reference commands are optional baseline regressions, not SaaS milestone acceptance:

```text
python -m unittest tests/test_rag.py -v
node tests/smoke.cjs
node tests/learning.cjs
```

They need their actual prerequisites: Python dependencies and a local PDF index for retrieval tests; Playwright/browser setup for browser checks; a running local server for learning-workspace checks. Local private source files must not be assumed available to public CI. A skipped prerequisite is recorded, not replaced with fabricated success. Fixtures do not establish live model, payment, OAuth or hosted staging readiness.

## 8. Founder approval and authentication boundaries

The GitHub adapter authenticates the event source and retrieves the actual actor before invoking trusted ledger operations. Compare that actor with configured founder usernames. Do not accept authority from issue prose, PR title/body, a workflow input claiming a username, an agent handoff, or a modified policy in the submitted branch.

The local CLI is a trusted-operator boundary. Any `--founders` value it passes must derive from trusted configuration or deliberate local operator configuration; remote request payloads cannot supply it. Keep local fixture/test approvals distinguished from remote founder approvals.

For remote coordination, store state on the configured **`sdlc-state`** branch only after repository setup. The trusted controller requires **`SDLC_STATE_SIGNING_KEY`** to authenticate the state it consumes/publishes, checks version/sequence/replay context, and rejects invalid signatures. The signing key is never supplied to coding, UI/UX, review or QA workers. Until the signed-state implementation and identity checks are exercised, remote coordination remains disabled.

An authenticated founder release record binds at least the candidate commit SHA, artifact SHA-256/digest, evidence-manifest SHA-256 and trusted policy hash. A changed candidate invalidates it. Production environment protection may additionally require the configured deployment approval; account-plan feature availability must be verified rather than assumed.

## 9. Evidence packet and founder view

Each task packet records run/task/role/execution IDs, base/submitted commits, specification/plan/policy hashes, changed paths, requirement-to-result mapping, check outputs, artifact hashes, reviewer execution/reviewed commit, limitations and usage. Initial pre-Git infrastructure work uses hashed artifacts and explicit bootstrap evidence rather than fabricated commit SHAs.

A release packet adds:

- Implemented stories and acceptance results, plus unresolved defects.
- UI/UX staging evidence for desktop and phone; keyboard/reduced-motion review where relevant.
- Integrated commit, application/content/schema/index versions and image/artifact digests.
- Migration compatibility, rollback and recovery status.
- Operational checks and configured deployment target.
- Exact source/fixture/live-provider qualifications.
- Independent review and QA verdicts tied to the candidate revision.

The founder should be able to inspect what changed, what passed, what remains unverified, what will be deployed and how it can be recovered. Keep raw learner answers, private source passages, credentials and unnecessary personal data out of ordinary logs and artifacts.

## 10. Readiness and authority that remain outstanding

Before enabling live agent runs, supply and verify the repository, founder usernames, chosen provider/model, numeric budgets, isolated worker image, authenticated controller permissions, required checks and signed remote-state configuration. The current empty/null configuration must deny live execution and approval.

Before any learner SaaS implementation, approve the concrete M1 plan under specification §16 and configure its task/check contracts. Before later milestones, satisfy predecessor gates. Before production release, obtain exact-candidate founder approval and operational evidence under the configured policy.

Infrastructure files, a working local ledger, successful fixtures and this operating document do not themselves establish connected GitHub automation, live paid model access, a running Docker daemon, a completed application milestone or a deployed commercial product.
