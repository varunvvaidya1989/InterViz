# M1 operations and evidence prerequisites — proposed

## Reconcile current state

The assigned Git baseline is `ba8062a750c83247d0694ac7febe4e0758d4bd85`. `automation/README.md`, current policy and `docs/operations/INFRASTRUCTURE_VERIFICATION.md` describe an implemented signed ledger, isolated workers, independent review, CI reconciliation and recovery pulse. Their reported hosted infrastructure results are source context, not checks rerun by this planning worker. Earlier statements in M1.md/agents README/master that no runner or Git baseline exists are stale. M1-LEAD-001 reconciles its assigned documentation after exact-plan approval. This worker changes none of those sources.

Current application gaps remain: empty required application check list, no staging/production deployment targets, registry/hosting configuration absent. Infrastructure CI, live model sandbox probes and static prototype tests do not establish authentication, SaaS CI or staged delivery. No approval is inferred from an issue or from infrastructure authorization.

## Bootstrap and protected configuration

1. Current CLI rejects all non-infrastructure tasks while application checks are unconfigured. After exact-plan approval, the explicitly infrastructure-kind workspace task creates actual package scripts and nonempty shell/health/service/browser smoke tests. Independent review and clean local checks cover this initial bootstrap while current infrastructure gates continue to apply.
2. M1-OPS-003 proposes a bounded protected patch to `.github/workflows/application-ci.yml`, `automation/policy.json` and `infra/staging`. The trusted controller/founder separately accepts protected changes; workers cannot waive checks, alter authority/limits or accept their own patch. A policy patch must not authorize its own merge.
3. Set `checks.application_configured=true` only when actual checks exist and execute. Register actual status-check names under `gates.required_application_status_checks` and real entries under `checks.application` matching supported check schema. Preserve existing infrastructure requirements. Configure trusted staging evidence adapter only after actual commands/targets are known. If a required path/configuration is outside approved scope, return it to lead/controller rather than bypassing policy.
4. Accepting a policy change changes the exact plan hash. Trusted controller must recompute/reapprove against the new policy before resuming dispatch; do not reuse the earlier approval. Demonstrate new CI jobs at current head and their required-check reconciliation, including bot-created PR behaviour, then allow dependent app integration. No missing tests or placeholder success may count as a passing check. Protected-config acceptance is an existing policy gate, not an extra conversational product approval.

## Application CI contract

Proposed job IDs (verify exact resulting status names): `application-lint`, `application-typecheck`, `application-unit-integration`, `application-e2e`, `application-build`, `application-i18n-security`. Commands: frozen install with pinned pnpm/Node, `pnpm lint`, `pnpm typecheck`, `pnpm test:unit`, `pnpm test:integration`, `pnpm test:e2e`, `pnpm build`, `pnpm check:i18n`, `pnpm check:security`. Scripts are to be implemented, not commands this planning task claims to have run.

Use isolated PostgreSQL/Redis and captured mail with synthetic accounts, no external mail or OAuth credentials in pull-request tests. Browser tests exercise complete app and library-supported test doubles; these results remain fixture evidence. Fail on empty suites, missing keys, type/build errors and actionable security scan findings. Capture test reports, screenshots/traces on failure, build digest and exact SHA with sensitive token redaction. Existing infrastructure jobs still execute for infrastructure changes. Re-run required integrated checks after combining accepted branches; PR checks alone do not verify combined staging candidate.

Learner container uses explicit source copy allowlist and non-root runtime; inspect output for private PDFs, prototype scripts, `.git`, `.sdlc`, automation and credentials. Build/install time network access does not authorize runtime access to development services. Isolated staging host/network must not mount controller checkout or secret stores.

## External configuration inventory

| Prerequisite | Responsible party / evidence before use |
| --- | --- |
| Container host, staging hostname/TLS, region | Operator selects simplest compliant available target; record region/residency, account owner, estimated costs, deployment API and approved access |
| Registry/artifact store | Operator provisions private write path; CI attests immutable digest, no credential in worker prompts |
| PostgreSQL and Redis | Managed or operator-maintained isolated services; connection/ACL/separate migration role, TLS and backup schedule tested |
| Email | Verified staging sender/domain and provider secret supplied through managed store; actual verification/reset/welcome delivery to authorized test mailbox |
| Google/GitHub OAuth | Operator registers clients with exact HTTPS staging callback URLs and supported scopes; secrets out of band; QA records actual successful and failed flows |
| Secret store and deployment identity | Managed runtime injection, least privilege, no production credentials, secret-redacted logs; controller signing/model credentials excluded |
| Observability and budget | Operator configures logs/error/traces/alerts, retention and access control; project spending controls + service budget before paid dispatch |
| Review devices | QA gets actual phone and desktop staging access; browser version/device and emulation label recorded |

These are operational dependencies, not invented credentials or claims that a particular provider is already available. Local synthetic work can continue within dependencies while operator provisioning proceeds. Staging acceptance cannot proceed until prerequisites are real. Temporary Systems Labs branding and original/synthetic fixtures avoid all five §14 product decisions.

## Deployment and recovery

Promote only independently reviewed, required-CI-passing integrated SHA. Build once, record immutable image digest and configuration version, scan image, run migration preflight with a fresh snapshot, deploy to isolated HTTPS staging, check readiness privately and liveness publicly, run smoke and acceptance journeys. Record URL, commit/digest, timestamp, migration and infrastructure version; screenshots alone do not establish deployment identity. Test secrets/log redaction and graceful Redis/mail/database failure responses. Never deploy production in M1 assignment.

Daily encrypted DB backups start with account storage; restrict backup access and set documented retention. Planning target RPO <=24 hours and restore target RTO <=4 hours, to be measured in drill rather than claimed. Before acceptance, create a backup containing synthetic test accounts, restore into separate staging DB, verify account/profile constraints and login/session policies, and replay deletions that occurred since snapshot. Keep original DB intact during drill. Record backup ID/time, recovered rows/invariants and measured duration. A scheduled backup definition alone is insufficient.

For compatible changes, redeploy prior image with forward-compatible schema and rerun health/auth checks. For incompatible migration failure, stop account writes, preserve failure evidence, restore verified pre-change snapshot into isolated replacement DB, replay deletion suppression, validate before controlled switch, and document any lost writes. Never automatically run destructive down migration or erase audit/deletion records. Recovery operations require operator capability; an implementation worker only supplies scoped proposals/evidence.

Request logs, safe health, error tracking and request tracing include candidate SHA and correlation IDs. Alert on auth/error spikes, mail failures, limit backend failure and failed backups. Document 99.9% availability target; a short staging run cannot prove it. Record mid-range phone/4G meaningful-content-paint measurement (<2.5 seconds target) with FCP/LCP support; M7 Lighthouse and M2 renderer timings remain later.

## Evidence manifest and release boundary

Each artifact records story/requirement/test ID, exact commit, build/image digest, environment class (`local`, `fixture`, `emulated`, `staging`, `live-provider`, `physical-device`), timestamp, command/procedure, observed result, redacted artifact location, reviewer and limitations. QA runs read-only under the current CLI; the controller/lead persists its returned report. Store operational evidence under `docs/releases/R-1/evidence/operations`; QA under `evidence/qa`. None exists yet.

Required outcomes include actual staged signup/verification/reset, Google and GitHub success, skip/save/edit/profile, privacy lifecycle, empty-dashboard accessibility and phone/desktop review, restore and rollback. Bugs return to originating owner within two implementation/review attempts. Revised candidate invalidates affected evidence. Missing provider/device/recovery evidence remains outstanding and blocks milestone acceptance. After accepted M1 update changelog and stop/report; production publication still requires configured deployment and separate exact-candidate founder approval.
