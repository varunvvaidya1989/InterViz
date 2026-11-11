# GitHub automation wiring

This directory wires the trusted `automation.cli` controller into GitHub Actions for `varunvvaidya1989/InterViz`, with founder `varunvvaidya1989` and Codex as the selected development provider. It creates no repository, secrets, branch rules, external infrastructure, staging application, or deployment. Keep `SDLC_ENABLED` unset/false until policy, identity, repository, state-signing, and adapter prerequisites are verified.

## Workflows and CLI contract

| Workflow | Purpose | Controller commands |
|---|---|---|
| `agent-control.yml` | Founder issue/comment events, controller-update push/scheduled reconciliation, queued lead/coding/UI/UX/DevOps/review/QA work | `state --action restore`; `event --event-name ... --event-path ...`; `worker --role ... --task-id ... --revision ... --event-path ...`; `reconcile --event-path ...`; `state --action save` |
| `infrastructure-ci.yml` | Read-only, secret-free PR/default-branch infrastructure checks | `python -m unittest discover -s automation -p 'test_*.py' -v`; `validate --scope infrastructure --revision ...` |
| `review-integration.yml` | CI/review facts, independent review, bounded debate/rework and exact-revision merge eligibility | `event`; queued `worker --role review`; `reconcile`; signed state restore/save |
| `staging-qa.yml` | Exact integrated-revision checks and QA findings/bug tickets | `validate --scope infrastructure|staging --revision ...`; optional queued `worker --role qa`; `reconcile`; signed state restore/save |
| `release.yml` | Founder-only candidate assembly/publication | `release --phase candidate|publish --candidate-id ... --revision ...`; signed state restore/save |

`doctor --format json` reports readiness and missing configuration. It is not evidence that application integrations are configured or that staging passed. Actual application staging validation must fail/return blocked until an approved real staging adapter and deployment revision are configured. The workflows contain no pretend deployment step.

## Required repository configuration

- `SDLC_ENABLED`: explicit string `true` only after bootstrap checks pass.
- `SDLC_TRUSTED_ACTORS`: JSON array of authorised GitHub logins; use `["varunvvaidya1989"]` for the initial founder-only human setup. Absent/empty means no human-triggered privileged work.
- `SDLC_FOUNDER_LOGIN`: `varunvvaidya1989`, used by the release workflow. The controller also verifies the policy/ledger founder and exact approval.
- `SDLC_STAGING_URL`: optional real staging endpoint; does not prove a deployment exists. The controller validates allowed origin and deployed revision before treating it as staging evidence.
- `SDLC_STATE_SIGNING_KEY`: managed secret used only by state restore/save. Preserve and rotate it through a documented state migration; do not expose it to model providers or worker subprocesses.
- Selected provider credential: `OPENAI_API_KEY`, passed only to the trusted Codex worker entrypoint. An optional Anthropic adapter can remain in the controller, but these workflows do not expose an Anthropic credential. Changing provider requires an explicit policy/configuration update. The controller must strip all GitHub/state-signing credentials from provider/model subprocesses.
- `founder-release` environment and any available approval/protection rules appropriate to the account. Environment availability varies by GitHub account/repository plan; controller-level founder approval remains mandatory.
- CODEOWNERS assigns every path to `@varunvvaidya1989`. Configure required default-branch rules and checks `sdlc-infrastructure-ci` and `sdlc-independent-review`; the file alone does not enable repository protection. Verify the configured rules through bootstrap/doctor.
- Seed the `sdlc:plan`, `sdlc:story`, `sdlc:bug`, and `sdlc:release-candidate` issue labels through an authorised bootstrap operation. Labels/forms themselves never approve a plan or release.

No secrets belong in issue bodies, workflow inputs, logs, state artifacts, or source control. GitHub tokens are available only to state/controller/publisher steps. PR CI has no model, signing, or deployment secrets and does not restore the privileged ledger.

## Trust and state requirements

Privileged workflow steps execute only the repository's trusted default-branch controller. Independent review receives the authenticated diff and a separate workspace checked out at the exact submitted PR head, allowing candidate inspection and sandboxed checks. Candidate code is never loaded as controller code. Reviewer role instructions and the Docker image come from the trusted default branch; the candidate is untrusted data. Before a queued worker/review/QA model step, the workflow builds `infra/Dockerfile.agent` as `systemslabs-agent:local` from that trusted checkout, without model/GitHub/signing credentials in the build step. Review receives an immutable Docker candidate mount at /workspace and writable scratch at /review and /tmp inside the restricted Codex sandbox, with no GitHub or signing credentials. Coding execution uses the controller's isolated worktree/tool policy; model subprocesses do not inherit privileged controller credentials.

The `workflow_run` notification is a signal, not trusted proof. Both successful and failed completed CI notifications are ingested so a later failure can invalidate eligibility. The controller must verify repository, workflow identity/path, source event, source head commit, conclusion, run/check IDs, task/PR linkage, required checks, and current revision through GitHub's API before accepting it. A matching display name or uploaded artifact alone is insufficient. Changed commits invalidate review and release evidence.

Bot dispatch is permitted only for the controller's previously queued, policy-valid task. The CLI must check queue/lease/run provenance before accepting `github-actions[bot]`; the actor name is not an independent approval. Reconciliation dispatches only authorised READY tasks against the trusted default branch.

All mutating workflows share concurrency group `sdlc-ledger`, with cancellation of running jobs disabled. State restore/save uses HMAC-authenticated snapshots on the dedicated `sdlc-state` branch and compare-and-swap updates through the controller. State metadata is not a secret store. Restore failure prevents save, so missing/untrusted state cannot be silently replaced with an empty ledger.

GitHub concurrency is not a durable queue: a newer pending run can replace an older pending run. Reconciliation therefore must rescan durable issue/comment/PR facts, deduplicate their identifiers, and recover skipped/replaced event notifications. Scheduled reconciliation is a recovery pulse, not the only record of an approval. Preserve interrupted task leases and require a new lease before retrying.

## Founder gates and evidence

Founder plan approval binds the exact plan revision and execution bounds. Independent review is separate from the coding author. Bounded debate/rework follows policy; exhausted rounds create a founder/lead decision need rather than an unbounded agent loop. Merge requires exact-current-commit evidence and does not equal release approval.

QA failure creates a reproducible, exact-revision defect under policy; blocked staging remains blocked. QA validates the requested `infrastructure` or `staging` scope, and the queued worker receives that scope through its event/policy contract. Release publication requires the founder's exact candidate/commit/manifest approval (`/sdlc approve-release R SHA MANIFEST_HASH`) and fresh applicable CI/review/QA evidence. Replace `R`, `SHA`, and `MANIFEST_HASH` with the candidate's exact published values. Candidate assembly, labels, issue checkboxes, fixtures, dry runs, and workflow dispatch by themselves never stand in for those facts.

Artifacts under `.sdlc/output/` are retained for the documented short interval. They contain redacted operational/test evidence, not the state ledger or raw private prompts. Changelog/release records must identify the integrated commit and clearly state infrastructure-only scope when the SaaS application has not been built.

## Action pin provenance

Action references were resolved from each official repository's remote tag on 10 November 2026:

- `actions/checkout` v5 → `fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09`.
- `actions/setup-python` v6 → `ece7cb06caefa5fff74198d8649806c4678c61a1`.
- `actions/upload-artifact` v4 → `ea165f8d65b6e75b540449e92b4886f43607fa02`.

Pins should be updated through reviewed PRs after checking the official release/commit and runner compatibility. No privileged `pull_request_target` checkout or artifact-to-shell execution is used. Official guidance: [secure workflow use](https://docs.github.com/en/actions/reference/security/secure-use), [workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), and [deployment environment protections](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).


## Retained submission recovery

The controller-update push event reconciles on trusted main so a reviewed recovery fix becomes effective without a manual command. Expired unchanged resubmissions may be restored only from a failed trusted controller run whose successful worker handed back the original exact candidate. Recovery verifies artifact SHA-256/provenance, worker/lease/approved-plan identity, original PR/current head and clean candidate bytes; artifact content is never extracted or executed. Download redirects remove the GitHub credential before reaching the HTTPS artifact host.

Signed ledger writes remain inside the serialized trusted controller. Old reviews and CI remain immutable but cannot satisfy the recovered submission's new evidence epoch. Independent review and fresh CI are dispatched within existing limits. Protected controller changes still require founder acceptance, and no recovery transition can merge, accept, deploy or reset attempt counts. Retention expiry or missing evidence is a lead recovery prerequisite, not a test pass.
