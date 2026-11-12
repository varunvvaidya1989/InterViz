# OPS104 first-publication recovery repair

Status: implementation proposal, not acceptance or integration evidence.

Base: de6555839f148eebdccbba9443f2f807de3fa8a2. Infrastructure authorized; the signed approved R-1 plan remains authoritative over older planning-only snapshots.

The lead assigns this repair exclusive temporary ownership of automation/control.py, cli.py, recovery.py, runtime.py, associated publication/recovery tests, automation/README.md and .github/workflows/agent-control.yml. The original OPS104 worker has stopped and its lease expired; no overlapping worker may edit these paths during this repair. The original five-file worker source is retained separately and is not modified by this repair.

Implement a founder-only hosted recover-publication command accepting an existing task, failed source run, exact candidate PR and SHA. Validate authenticated run/artifact/digest/timing, original worker lease, current approved plan, bounded source bundle, direct parent and exact candidate tree before restoring the first submission. Preserve attempts, review/CI history and author identity; require fresh independent review and CI. Keep unchanged-resubmission recovery separate.

Optional SDLC_PUBLISH_TOKEN is supplied only to the trusted reconcile step and used only for Git push; workers, ledger signing and normal API calls keep their existing credentials. Missing workflow-write credentials remain a truthful external prerequisite. Git failure messages expose only fixed operation/reason labels.

No schema migration, application implementation, budget changes or approval bypass. Tests cover provenance, source tampering, active/stale lease, replay after rejection, rollback, author independence, token isolation and secret-safe diagnostics. Run relevant unit tests and full infrastructure suite before submission. Protected exact-code founder acceptance and independent review remain required before integration.


The recovery command may receive an explicitly founder-accepted infrastructure CI blob SHA. Acceptance is a separate audited receipt bound to the current plan/task/PR/head/epoch and fixed workflow path; absence or mismatch preserves the existing CI-definition trust denial. The receipt only authorizes the reviewed definition to supply real run results, never waives checks.
