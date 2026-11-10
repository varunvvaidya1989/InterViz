# Founder-controlled SDLC infrastructure

Repository: https://github.com/varunvvaidya1989/InterViz

The founder supplies direction and release scope. The lead prepares stories, UX, architecture, operations and tests. The founder approves the exact plan. Isolated Codex workers propose PRs; independent review and verified CI precede merge. Integrated staging QA creates bug tickets and routes work back to developers. A tested candidate is frozen for the founder's second approval before release notes/publication.

## Implemented infrastructure

- Transactional SQLite ledger with immutable audit chain and restart-safe records.
- Exact plan/scope approval, independent current-head review/CI, task leases/path ownership, two-attempt rework, QA bugs and exact-candidate release approval.
- Signed GitHub `sdlc-state` snapshots with compare-and-swap updates. Controller state is separate from learner data.
- Docker-contained Codex workers, default-branch controller code, diff-only independent review, clean-clone publication, scoped file checks and protected policy/infrastructure paths.
- GitHub issue forms, CI, agent control, review/integration, staging-QA and founder-release workflows.
- Explicit CI dispatch for bot-created PRs, plus durable reconciliation of CI and founder-comment facts. A scheduled recovery pulse handles coalesced Actions events.

## Founder workflow

1. Open the **Founder plan** issue form and describe the release outcome, included/excluded work and milestone. Add/retain `sdlc:plan`.
2. The lead proposes `docs/releases/R-<issue-number>/plan.json` and related UX/architecture/operations documents in a PR. Review these first. The controller posts the exact approval command.
3. Approve with `/sdlc approve-plan RELEASE PLAN_HASH`. Editing stories, the specification or policy invalidates it.

   Before implementation begins, request changes with `/sdlc revise-plan RELEASE describe the changes`. This withdraws the previous approval and sends your feedback and previous plan to the lead. Started releases require an explicit amendment, preserving their existing work. Repeated unsuccessful planning attempts escalate rather than looping indefinitely.
4. Follow linked PRs, checks, bounded review comments and bug tickets. Protected controller/policy changes require separate founder acceptance; they cannot authorise their own automatic merge.
5. After actual staging QA passes, run **SDLC - Founder release**, phase `candidate`, with release ID and exact integrated commit. Review its candidate manifest and changelog.
6. Approve with `/sdlc approve-release RELEASE COMMIT MANIFEST_HASH`.
7. Publication remains gated on actual deployment configuration, current QA and matching approval. The scaffold cannot report an undeployed SaaS as released.

For an already committed reviewed plan, `/sdlc plan docs/releases/<release>/plan.json` imports it into the ledger. Plans require `release_id`, `user_stories`, `ui_ux`, `architecture`, `operations`, `acceptance_tests`, and `delivery_tasks`. Every story defines stable ID, title, role, allowed paths, acceptance criteria and dependencies. Use `kind: infrastructure` only for explicitly authorised infrastructure scope.

## Setup and controls

The founder is `varunvvaidya1989`; the selected provider is Codex. `OPENAI_API_KEY` and `SDLC_STATE_SIGNING_KEY` belong in repository secrets. They are not stored in tracked files or images. Model steps receive no GitHub token or controller signing key.

Repository variables: `SDLC_ENABLED`, `SDLC_TRUSTED_ACTORS` (JSON array), `SDLC_FOUNDER_LOGIN`. `infra/bootstrap_github.py --configure` verifies the existing authenticated account and configures these plus the signing secret. It never rotates an existing signing key silently.

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
