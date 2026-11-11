# Local founder dashboard

Run from the repository root:

```powershell
python -m founder_dashboard.server --open-browser
```

Or double-click `Start-Founder-Dashboard.cmd`. Open http://127.0.0.1:8010. The dashboard is separate from the prototype on port 8000 and needs no additional Python packages.

Git Credential Manager's existing GitHub sign-in is used, or a locally configured `GH_TOKEN`/`GITHUB_TOKEN`. Credentials remain on the Python server and never enter browser code. The server binds only to loopback, validates Host/Origin, serves only its own assets, and reads GitHub state. Refresh updates the local cache. The explicit Approve plan and Approve release buttons dispatch the trusted founder approval workflow; they never write the controller ledger, merge PRs or edit tickets locally. No command comments or copied hashes are required.

The current ledger supplies release scope and task identity. Open GitHub issues outside that scope are excluded from progress. Integrated means merged; it does not mean the release passed QA. Dependency waits are separate from blocked work. Expired leases, exhausted attempts, requested changes, workflow approval waits and missing planning-PR review checks surface in the attention list. Task details include acceptance criteria, allowed paths, dependencies, attempts and evidence links.

GitHub data refreshes every 60 seconds in the background. The page polls the local cache every four seconds. Last successful refresh and ledger save times are shown independently; failed refreshes retain the last known data with a warning, never a fabricated success. A running worker may not appear in the ledger until it saves its snapshot; the workflow activity panel shows running Actions in the meantime. Recent workflow history is bounded to 40 source runs (20 displayed), controller events to 60 and active PR details to 30. Display times use Asia/Kolkata.

Remote snapshot checksums are verified before SQLite is deserialized into an isolated in-memory, query-only connection. Authentication comes from GitHub. If `SDLC_STATE_SIGNING_KEY` is already provided locally, the HMAC signature is also checked; otherwise the dashboard does not claim local signature verification. The key is not needed by the dashboard; signed approval writes happen only in the hosted controller. It never opens the writable controller database.

Stop with Ctrl+C in its terminal. No public hosting or learner-app integration is configured.

## Verification

```powershell
python -m unittest founder_dashboard.test_dashboard -v
node founder_dashboard/browser_check.cjs
```

The browser check uses a locally installed Playwright module (or `PLAYWRIGHT_MODULE`) and an existing Chromium browser (`CHROMIUM_PATH` when needed). Test-only tooling is under ignored `.tools/dashboard-qa`; it is not a runtime dependency. Screenshots are under ignored `artifacts/`. Checks cover live counts, filtering, list/board views, keyboard drawer dismissal, mobile reflow, cached-data errors, HTML escaping and absence of external browser requests.


## Founder decisions

The approval panel shows the complete plan scope or frozen release summary. Select Approve plan to authorize that exact plan, or Approve release after exact integrated QA. The server attaches all identifiers. Requests show as pending until confirmed in the signed controller snapshot, and failures/changed versions remain visible. Repeated clicks are deduplicated. Only the configured founder can dispatch; other signed-in accounts see disabled controls.

Activation requires the reviewed founder-approval.yml and controller code on trusted main. Until then, the panel states that approvals are unavailable. Existing approved plans do not need another approval because an unrelated task is stuck. Exhausted attempts remain lead/controller recovery work, not a new approval demand.

The release button records approval even when production is disabled, and says explicitly that publication remains unavailable. It cannot enable production or skip tests, independent review, QA, protected-path acceptance or task limits. New approval labels and messages use static/en.json. Legacy dashboard labels predate this change and remain in their existing files.

New verification: `python -m unittest discover -s founder_dashboard -p "test_*.py" -v` and `node founder_dashboard/approval_browser_check.cjs`. Browser checks intercept approval requests with synthetic fixtures and never approve a live plan or release.
