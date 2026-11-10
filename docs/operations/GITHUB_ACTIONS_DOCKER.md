# GitHub Actions and Docker automation design

Prepared 10 November 2026. Status: proposed integration for the specification-derived delivery pack. No workflows, images, registry pushes or deployments have been activated by this document. Product milestone order and the M1 approval gate remain unchanged.

## 1. Recommendation

Use **GitHub Actions for coordination and checks**, **Docker for repeatable worker/application environments**, GitHub branches/PRs for reviewed changes, and a registry for immutable application images. Keep the lead's decisions and task evidence in the management contracts rather than embedding uncontrolled agent conversations in workflow YAML.

Two workflows are related but distinct:

1. **Agent development:** approved task → lead decomposition → dependency-ready role workers → independent review → proposed PR.
2. **Application delivery:** PR checks → reviewed merge → immutable image → staging → acceptance/release policy → production verification.

GitHub Actions supports manual/event-triggered workflows, deployment environments and concurrency controls. Docker documents image building/caching integration with Actions. See [GitHub deployment guidance](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments) and [Docker Actions integration](https://docs.docker.com/build/ci/github-actions/).

## 2. Agent flow

```text
Owner-approved milestone / validated task selection
  → GitHub manual dispatch (later: trusted issue-label dispatch)
  → validate task IDs, spec/plan hashes, dependencies and budgets
  → lead creates bounded assignments
  → run dependency-ready workers in isolated Docker workspaces
  → collect commits, handoffs, usage and artifacts
  → independent QA/design review of exact revisions
  → lead integrates accepted outputs and proposes a PR
  → ordinary application CI and staging evidence
```

Start with explicit `workflow_dispatch` task selection. Issue-triggered execution can follow once trusted actor/label and approval checks exist. Issue text is untrusted task data, never a shell command or an authority to change milestone gates.

Role jobs consume `agents/backlog.json`, `agents/requirements.json`, the assigned role brief, the current milestone plan, and an execution contract. Worker calls return a handoff conforming to `agents/task.schema.json`; “done” text is insufficient.

GitHub Actions does not itself provide a language model or an agent tool loop. A trusted worker adapter still needs implementation, model access, bounded tool execution and durable checkpoints. Existing chat-agent sessions do not automatically become GitHub runner jobs. Provider credentials and development-model spending are configured separately from the learner's Anthropic coach.

## 3. Proposed workflow files

These are implementation targets, not files claimed to exist yet:

| File | Trigger | Responsibility |
|---|---|---|
| `.github/workflows/agent-dispatch.yml` | Manual approved task/milestone selection | Check approval/plan/spec versions, validate tasks and prerequisites, assign an allowed batch |
| `.github/workflows/agent-worker.yml` | Reusable trusted workflow | Start isolated role worker with scoped inputs/tools; capture commit, handoff, cost and evidence |
| `.github/workflows/ci.yml` | Pull request and reviewed branch updates | Frozen-lock install, lint/types, unit/integration, content checks, migrations, E2E, accessibility and relevant performance checks |
| `.github/workflows/images.yml` | Accepted protected-branch revision | Build/test application image, produce provenance/SBOM as configured, publish immutable commit tag and image digest |
| `.github/workflows/staging.yml` | Successful image build | Deploy exact digest, run compatible migrations once, health/smoke/browser checks and attach environment evidence |
| `.github/workflows/release.yml` | Release decision under configured policy | Promote the tested digest to production; verify health and record previous/active release |
| `.github/workflows/reconcile.yml` | Scheduled after M4 exists | Reconcile payment/access facts with bounded retries and audit records |
| `.github/workflows/recovery-check.yml` | Scheduled/manual isolated exercise | Demonstrate backup restoration/rollback without touching live learner data |

Do not create active payment/tutor/reconciliation jobs before their owning milestone. The workflow list is a target architecture, not permission to front-run M1–M8.

## 4. Docker responsibilities

### Development worker image

Pin the OS/runtime/package-manager and agent adapter versions. Supply Git, the compatible Node/pnpm toolchain, test/browser dependencies and only the tools assigned to the role. Each modifying task has its own checkout/branch and workspace volume. Use non-root execution and bounded CPU/memory/time where supported.

The trusted adapter is versioned separately from generated changes. Worker repository files are untrusted inputs. Do not let a proposed patch select its own credentials, broaden tools, edit the protected adapter, or change acceptance gates. Docker is an execution environment; it does not replace tool, network, secret and repository permission enforcement.

### Local development services

Compose runs application dependencies consistently: PostgreSQL, Redis and captured development email. Databases use named durable storage locally; CI uses disposable isolated test data. No production snapshot is required for ordinary agent or CI jobs.

### Learner application image

Use a multi-stage build with a locked dependency install, test/build stages and a minimal runtime stage. Keep development agents, private source PDFs, secrets and test artifacts out of the production image. Add a safe health/readiness contract. Pin the resulting image by digest and promote the same tested artifact; do not rebuild different code during production promotion.

Actual image package versions/digests and build action references are verified/pinned during M1, not copied uncritically from this plan.

## 5. Concurrency, state and recovery

- Retain the initial capacity of one lead plus three workers; dependencies determine who may run.
- Use task/run IDs and concurrency groups to prevent duplicate task execution and overlapping environment deployments.
- Use separate branches/checkouts per modifying task. The pre-Git bootstrap remains limited to the two approved initial tasks.
- Use one owner for shared manifests, migrations, global tokens and contracts.
- Save task inputs, exact commits, handoffs and evidence as durable records/artifacts. CI job memory and chat history are not the source of truth.
- A cancelled/retried job must reconcile its task lease and external mutations before resuming.
- Serialize deployments and migration ownership for an environment. A cancelled test run is not a reason to cancel an in-progress production migration.
- Bound worker attempts, model calls/tokens, runtime and spend. Two unsuccessful work/review cycles return findings to the lead.

For an initial managed batch, GitHub run artifacts plus reviewed commits and a lead-maintained task ledger can record checkpoints. A later unattended coordinator needs atomic task leases/transactions in a separate control-plane store. Do not silently use the student application's tables as the agent control plane.

## 6. Credentials and repository policy

- Store provider and deployment credentials in appropriate GitHub/environment secret stores, injected at execution time. Never place them in images, tracked files, issue text, user-visible logs or worker handoffs.
- PR validation jobs run without production credentials. Do not execute untrusted proposed code under privileged deployment/model jobs.
- Use read-only permissions by default; separate code/PR publication and deployment permissions into their narrowly authorised jobs.
- Resolve application ownership and protected-branch/CI policies during M1. Work generated by an agent is still reviewed through the same exact-revision gates.
- Keep deployment environment access and the first production release subject to the agreed release policy. Required-reviewer features depend on the repository/account plan; choose supported protections rather than assuming availability.
- The hosted coach credential rejected during prototype development does not prove that development-agent model access is configured.

## 7. Acceptance before calling automation operational

1. An approved bounded task dispatches through the selected model adapter and produces a committed, reviewable change.
2. Restart/retry preserves state and does not create duplicate tasks, PRs or deployments.
3. Unit/E2E/content/security checks run against the exact proposed revision and can block it.
4. Independent QA can reject and return a task for bounded rework.
5. A reviewed merge builds a traceable image; staging runs that exact digest with health/migration evidence.
6. Deployment failure has a tested recovery path that preserves learner data.
7. Secrets are absent from images/logs/artifacts and unnecessary job contexts.
8. Production requires its configured release decision; automation does not imply unrestricted deployment authority.

## 8. Current setup status

Docker and Git command-line executables were found locally. Docker daemon availability was not tested. This workspace still has no Git baseline/remote, and GitHub CLI was not found in the current PATH. No GitHub repository/account access, action secrets, registry or hosting destination has been configured by this planning task.

The immediate implementation point remains approved M1: establish the baseline, workspace/toolchain, Compose/CI checks and a containerized staging foundation. The unattended agent adapter and its operational acceptance are a distinct infrastructure assignment; their implementation must not delay or be falsely counted as learner feature acceptance.
