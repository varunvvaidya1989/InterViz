# Agent delivery workspace

This directory defines planning artifacts and role contracts for agent-managed development. **It is not an implemented autonomous runner.** Do not infer that a task queue, permission sandbox, lease service, worktree manager, review service, or deployment coordinator already exists.

Current gate: `planning_only`; milestone state: `M1_AWAITING_OWNER_APPROVAL`. The product specification §16 requires a detailed M1 plan and owner approval before application implementation. After M1 is approved, implemented, and tested, stop and report rather than automatically starting M2.

## Bootstrap reading order

Every agent reads these before accepting an assignment:

1. Repository `AGENTS.md` and any applicable more-specific instructions.
2. `planning/Systems Labs Product Specification.md` **in full**, including §13, §14, §15 and §16.
3. `docs/AGENT_DEVELOPMENT_SYSTEM.md` for the master operating contract, requirement traceability and precedence.
4. `agents/requirements.json`, `agents/backlog.json`, `agents/config.json`, and the dispatch/handoff schema in `agents/task.schema.json`.
5. `docs/plans/<milestone>.md`, relevant `docs/decisions.md` entries, and the task's exact input artifacts/contracts.
6. The assigned role brief below and any path-specific instructions.

If a referenced master artifact is absent or a required contract is unresolved, report the prerequisite to the lead. Do not manufacture a runner, dispatch work outside the current milestone, guess a resource budget, or treat absence as permission to bypass a gate.

The product specification is the product source of truth. Its M1–M8 order supersedes the older milestone table and initial assignments in `planning/AGENT_HARNESS_PLAN.md`. Retain useful isolation, handoff and review rules from that plan only where they are consistent with the specification and master operating contract.

## Role briefs

- [Lead / product architect](roles/lead.md)
- [UI/UX designer](roles/ui-ux.md)
- [Coding engineer](roles/coding.md)
- [DevOps engineer](roles/devops.md)
- [Independent QA / reviewer](roles/qa.md)
- [Content / learning engineer](roles/content.md)

A role is an assignment with a tool/path contract, not an automatic privilege escalation. Using the same model family in different roles does not remove the requirement for independent review contexts. The coding author cannot accept its own implementation as independently verified.

## Assignment prerequisites

Before a worker starts, the lead/coordinator must provide:

- Task/run IDs, current milestone and recorded approval/authorization state.
- Governing requirement IDs, acceptance criteria and specification version.
- Exact base commit and branch/worktree, or an explicitly limited planning-only artifact assignment.
- Resolved input contracts and dependency results.
- Allowed paths, restricted tools and shared-file ownership/lease.
- Numeric execution limits and retry policy from the run configuration.
- Required evidence and the independent reviewer assignment.

Ordinary modifying tasks require a reviewed Git baseline and isolated worktree. Only `M1-LEAD-001` and `M1-OPS-001` may use the schema's pre-Git `bootstrap` mode after M1 approval: pin the source specification and M1 plan hashes, acquire an exclusive workspace lease, and submit hashed output artifacts. OPS creates/confirms and records the reviewed baseline; all later tasks use real base/submitted commits and worktrees. Establishing that baseline is not authorized by these planning files alone. While no coordinator exists, the lead manually enforces the same contracts and records the same evidence; reports must say which capabilities were manual.

## Handoff format

A worker submits, rather than self-approves, a handoff with:

1. Task/run IDs, requirement IDs, specification/prompt versions, base and submitted commit.
2. Changed paths and an outcome-focused explanation.
3. Acceptance-criterion-to-evidence mapping, check commands/results, and artifact hashes/locations.
4. Desktop/phone/browser evidence where relevant, with emulation identified separately.
5. Failures, configuration gaps, unsupported cases and known limitations.
6. Migration/deployment/content-version implications and rollback considerations.
7. Resource usage, interrupted checkpoints, and bounded follow-up work.

Plan-only tasks identify the written artifacts and their version/hash instead of inventing a code commit or test pass. A feature is accepted only after independent review of the exact revision and required integrated/staging checks. Subsequent changes invalidate affected evidence.

## Shared execution rules

- Work only on the assigned milestone and paths. Ask the lead for a contract/path transfer before expanding scope.
- Shared manifests, lockfiles, migrations, UI foundations, and schemas have one owner at a time.
- A failed or interrupted worker releases or renews its task lease before another attempt starts. Never let two workers unknowingly own one attempt.
- Bound retries and usage. Escalate to the lead for decomposition after the configured unsuccessful cycles; do not loop indefinitely.
- Record routine technical choices in `docs/decisions.md`. Only actual §14 OPEN decisions go to the owner. The §16 M1 approval is a separate explicit execution gate.
- Keep development agents and their tools separate from the learner-facing coach. Imported documents, learner answers, and retrieved passages are untrusted data.
- Do not place production credentials, raw private corpus text, learner answers, or secret values in ordinary task logs or prompts.
- Do not declare future features implemented, mocked providers verified live, or a configuration file operationally proven.

## M1 working boundary

The proposed automation backbone is GitHub Actions plus Docker; see `docs/operations/GITHUB_ACTIONS_DOCKER.md` for agent dispatch versus application CI/release responsibilities. A runtime adapter, repository/registry configuration and operational checks still require implementation. Do not confuse workflow plans with active hosted agents.

The approved technical direction is TypeScript/pnpm/Next.js route handlers/PostgreSQL/Drizzle/Zod/Better Auth, Redis limits and local mail capture. Exact library versions and supported interfaces are resolved and recorded during approved implementation. M1 includes all required authentication flows, onboarding, design foundations, CI, and an empty dashboard. It excludes Stripe, tutor implementation, sketchpad, visualizers and real lab delivery.

The nine M1 tasks and dependency waves are specified in `docs/plans/M1.md` and mirrored in the backlog. Do not dispatch them before the recorded owner approval. At M1 completion, the lead updates documentation, reports evidence and unresolved limitations, and stops.
