# Founder-controlled SDLC infrastructure

Repository: https://github.com/varunvvaidya1989/InterViz

The founder supplies direction and release scope. The lead prepares stories, UX, architecture, operations and tests. The founder approves the exact plan. Isolated Codex workers propose PRs; independent review and verified CI precede merge. Integrated staging QA creates bug tickets and routes work back to developers. A tested candidate is frozen for the founder's second approval before release notes/publication.

## Implemented infrastructure

- Transactional SQLite ledger with immutable audit chain and restart-safe records.
- Exact plan/scope approval, independent current-head review/CI, task leases/path ownership, two-attempt rework, QA bugs and exact-candidate release approval.
- Signed GitHub `sdlc-state` snapshots with compare-and-swap updates. Controller state is separate from learner data.
- Docker-contained Codex workers, default-branch controller code, exact-revision independent review, clean-clone publication, scoped file checks and protected policy/infrastructure paths.
- GitHub issue forms, CI, agent control, review/integration, staging-QA and founder-release workflows.
- Explicit CI dispatch for bot-created PRs, plus durable reconciliation of CI and founder-comment facts. A scheduled recovery pulse handles coalesced Actions events.

## Founder workflow

1. Describe the outcome in the **Founder plan** issue form. Agents prepare the scope, architecture, operations and tests.
2. Open the local founder dashboard (`python -m founder_dashboard.server --open-browser`). Review the plan summary and select **Approve plan**. No command comments, release IDs or hashes need to be typed.
3. Agents build, independently review, test and integrate approved work. The dashboard distinguishes an agent recovery problem from a founder decision; approval does not reset exhausted task attempts.
4. Once integrated QA passes, the controller prepares the release candidate automatically. Review its summary and select **Approve release**.
5. When production publication is configured and authorized, the controller requests publication of that exact approved candidate. A disabled production target remains clearly disabled; approval never invents deployment evidence.

A click queues a request. The dashboard shows **Approval requested** until the trusted controller saves the exact approval in signed state. Failed/stale requests remain visible with evidence and retry guidance. Only the configured founder's authenticated GitHub identity may request approval. If the plan or candidate changes, the old click cannot approve the replacement.

The dashboard is loopback-only. Browser requests use same-origin checks and a per-server CSRF token. GitHub credentials remain on the Python server; the server dispatches the trusted `founder-approval.yml` workflow and never writes/signs controller state itself. That workflow must first be independently reviewed and merged into trusted `main` before the buttons are active. Existing command comments remain a compatibility path, not a required founder operation.

Protected controller/policy changes still need their separate founder acceptance and exact automated evidence. This UI does not waive branch protection, CI, independent review, QA, scope or production configuration.

## Setup and controls

The founder is `varunvvaidya1989`; the selected provider is Codex. `OPENAI_API_KEY` and `SDLC_STATE_SIGNING_KEY` belong in repository secrets. They are not stored in tracked files or images. Model steps receive no GitHub token or controller signing key.

Repository variables: `SDLC_ENABLED`, `SDLC_TRUSTED_ACTORS` (JSON array), `SDLC_FOUNDER_LOGIN`. `infra/bootstrap_github.py --configure` verifies the existing authenticated account and configures these plus the signing secret. It never rotates an existing signing key silently.

After bootstrap CI passes, `python infra/bootstrap_github.py --protect` installs the main-branch CI/review requirements. GitHub's combined bot PR creation/approval setting is enabled to permit worker PRs; the controller uses independent execution identities and check runs rather than bot self-approval. Founder administrators retain an emergency override. Checks target each proposed head; integrated staging QA verifies the combined result before release.

Application checks and real staging/production targets are intentionally unconfigured because the new SaaS is not implemented. The M1 implementation must add real checks and deployment evidence. The earlier prototype's tests cannot stand in for SaaS acceptance.

The initial GitHub controller serialises ledger-mutating jobs; it is not a high-throughput parallel task server. Scheduled rescanning recovers event pulses that Actions concurrency may coalesce. Larger workloads can later move leases/state to a dedicated transactional control-plane service.

Time, attempt and worker resource caps are enforced. The Codex CLI does not provide a hard per-task USD cap here; `max_cost` is an allocation/reporting target, not a claim of pre-spend enforcement. Configure OpenAI project spending controls and watch usage. Live provider verification establishes connectivity, not full application or production acceptance.

## Local verification

```powershell
python -m unittest discover -s automation -p "test_*.py" -v
python -m automation.cli validate --scope infrastructure
python -m automation.cli doctor --format json
docker compose -f compose.sdlc.yml run --rm controller-check
```

The ledger API can also be exercised through `python -m automation.control --help`. Local fixture identities do not authenticate remote founder approvals; the GitHub controller verifies workflow actors and API facts.

## Current boundaries

No real SaaS story or release plan has been approved by this bootstrap. Stripe, learner auth, app containers, hosting targets and commercial launch remain their own specification milestones. Live agents cannot skip those gates. Source PDFs, secrets, local state, tools and screenshots remain excluded from the repository/image where configured.

## Recovering review and approval-waiting CI

Independent review checks the queued exact candidate in an isolated read-only sandbox; the controller and reviewer role instructions stay on the trusted default branch. If an older controller reviewed only a diff against main, integrate the independently reviewed controller repair before requesting another bounded review. Exhausted attempts need lead/controller rework; do not edit signed state to reset them.

GitHub action_required means a maintainer must approve the workflow before tests run. The controller does not treat this as executable CI evidence or consume its run receipt. Existing completed-run receipts remain unchanged to prevent historical replay. For a run already consumed by the older controller, dispatch a fresh CI run; attempt-level receipt migration is deferred. Existing failure records are not rewritten locally. Hosted CI and exact-revision review must both pass before protected integration.


## Automatic recovery of unchanged resubmissions

A rework worker may correctly report that its existing candidate needs no code changes. If it resubmits the exact previously recorded PR/head under its current task lease, publication restores that submission instead of rejecting an empty diff. Initial tasks with no prior candidate still require real changes.

For an older interrupted publication, the trusted controller can recover the retained unchanged handoff after its lease expires. It verifies the failed default-branch controller run, successful worker step, matching failed publication, artifact digest/provenance, exact worker/lease/task/plan and original PR head. It compares the entire recorded baseline against a clean candidate checkout. Missing, expired or mismatched evidence does not authorize recovery.

The transition preserves attempts, budgets and historical reviews/CI. A fresh evidence epoch requires fresh exact-head independent review and a new CI run; no old success is reused. Recovery has at most the configured two attempts per interrupted lease and cannot reopen a subsequent genuine review rejection. Audit-backed scheduling-cache cleanup survives an interrupted recovery. Exhausted/expired leases that cannot recover are escalated to the lead.

After an infrastructure controller update is reviewed and merged to main, the push event runs reconciliation immediately; scheduled reconciliation remains a fallback. No founder command comment, copied hash, counter reset or local signed-state edit is needed. Protected-path acceptance still governs merging the recovered PR; restored submission is not acceptance or milestone completion.


## Review fixtures and environment failures

Review/QA candidates are Docker read-only mounts at /workspace. The harness output directory is mounted separately as writable /review, the agent working directory, with /tmp available for test fixtures. Codex uses network-restricted workspace-write within those container bounds; this does not make candidate source writable. Python bytecode writes are disabled. Before any paid call, a key-free nested sandbox probe creates a SQLite fixture and confirms candidate writes fail.

Review commands use `git -C /workspace` and `PYTHONPATH=/workspace python3 -B`. Read-only source remains verified by the post-run scan. A blocked test environment with no confirmed code findings is recorded as unavailable evidence, not a code rejection; the required review check stays unsuccessful and the ledger cannot accept old evidence. Genuine defects still require rework.

The lead-corrected contract immutable-candidate-writable-fixtures-v1 has its own existing two-attempt bound. Legacy attempt receipts remain unchanged. One automatic correction may reopen only a latest legacy BLOCKED review with empty findings and no other confirmed current-epoch rejection, on the same exact approved head/contract. The new epoch requires fresh review and CI. A repeated genuine rejection cannot be cleared by this correction. No coding attempt, approval, scope or budget is reset.
