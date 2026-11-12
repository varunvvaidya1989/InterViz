# M1 task model, estimates and release acceptance

Planning revision responding to all four founder blockers. Only docs/releases/R-1 changed. Controller/application changes are proposals, not implemented prerequisites. This worker cannot publish a PR, merge/push, use GitHub APIs or change policy/approvals. Trusted controller must publish revised planning PR and freshly computed approval command after independent planning review.

## Flat task graph and outcome mapping

plan.json is authoritative: four `product_stories` retain learner/platform outcomes and acceptance; their `child_tasks` reference 36 concrete executable `user_stories`. Controller already adopts every user_stories entry via upsert_story into an ordinary story item. It ignores parent metadata; no nested scheduling is assumed. No QA/final-acceptance item is imported. Stable child IDs replace prior coarse IDs only before implementation starts; trusted controller must verify no attempts. Started releases cannot use destructive revise-plan; changed graph would require separately scoped general amendment support.

Graph is intentionally serial: OPS-101 → 102 → 103 → 104 → 105 → 106 → 107 → 108 → 109 → 110 → LEAD-101 → UX-101 → UX-102 → CODE-101 through CODE-118 → OPS-111 through OPS-115. No implicit parallel shared writers. This sacrifices throughput for deterministic base/lease ownership. One lead + up to three workers remains the ceiling, not a promise of four simultaneous tasks. Independent review can use an available slot against the exact submitted revision. All implementation dependencies mean independently reviewed/integrated, not SUBMITTED.

Every task in plan.json lists concrete owned paths, acceptance, tests, role, requirements and estimate. Proposed paths pass current policy allowlists with infrastructure=true only for explicitly infrastructural scope. Controller/workflow/infra edits remain protected; founder acceptance and independent review are separate from plan approval. No protected patch certifies or authorizes itself. CI/CLI shared files serialize through OPS-101–106; manifests/lockfile through OPS-107/108; UI/tokens through CODE-108/109; schema/migration through CODE-101/102. i18n mail/auth namespaces serialize; profile/dashboard/privacy own separate files. Broad directory leases remain exclusive and only for the listed bounded deliverable. New dependency/manifests or schema edits require recorded lease transfer and, if contract changes materially, approved amendment; no silent expansion.

Task base is exact current accepted integration commit resolved at dispatch; target_revision in manifest is planning source only. Existing Git baseline is real. Use isolated worktrees/branches and record source/plan/policy versions. Do not invoke pre-Git exception or edit prototype. Final staging deploy/QA targets latest combined candidate after all implementation evidence commits, not an earlier receipt.

## Estimates and limits

36 fixed slices, 12–18 worker minutes each, total 597 first-pass worker minutes (about 10 hours serial implementation effort, excluding reviews/QA/operator waiting). Each attempt timeout ≤20 minutes, model budget ≤100000 tokens, $2 allocation, maximum two implementation attempts/two review rounds and four discussion messages per round under current policy. $72 first-pass / $144 two-attempt allocation excludes independent reviewers, QA, external host and operator work; it is not a hard provider spending cap. Operator must resolve overall programme allocation/project controls before paid dispatch. Review sessions estimated 5–12m/task; release QA one 18m read-only assessment per candidate, at most two attempts under the current worker bound, final acceptance 12m. Automated suites and operator-recorded live/provider/recovery/physical-device evidence must be collected before that assessment; QA verifies provenance and performs targeted independent manual journeys. This does not assume a multi-session QA scheduler. If full verification cannot fit, return incomplete and commission separately bounded lifecycle support through a material plan amendment; never silently add sessions. All evidence requires one unchanged candidate; failures invalidate affected matrix, not reset session/bug attempt limits.

Estimates are concrete scopes, not promises of completing full identity or recovery in one 20m task. Meaningful tests belong to each slice. If task cannot finish within bound, checkpoint and submit limitation; after two attempts return evidence to lead for a material supported amendment rather than extra unbounded sessions, renamed IDs or reset attempts. External provisioning may take days and is not included in worker runtime.

## Release stages outside item gate

1. All 36 stories and any bug items independently reviewed, current-head CI passed, integrated. All external prerequisites resolved. Controller builds immutable final candidate, combined app CI, deploys/inspects/validates actual staging and stores matching receipt outside source.
2. `M1-QA-STAGE`: controller invokes existing start_qa at exact integration SHA, dispatches independent read-only QA through staging-qa. All authors excluded from independent certification. No QA story awaits integration. Failed report creates bounded scoped bugs linked to original task/developer. Bugs integrate only after independent review and real current-head CI; new integrated candidate is deployed and QA restarted. Old QA/candidate approvals invalidate. Model PASS without actual matching staging validation never completes QA.
3. `M1-ACCEPTANCE-STAGE`: only after matching complete_qa PASS and full §15 evidence, lead checks matrix and independent report review; controller persists acceptance/changelog stage artifacts in signed evidence. These artifacts do not become unfinished implementation items or mutate the tested candidate. If source must change, integrate it and rerun affected candidate checks/QA before acceptance. No production action or M2 follows.

QA report destinations `docs/releases/R-1/evidence/qa` and acceptance/changelog report destinations `docs/releases/R-1/evidence/acceptance` are controller persistence destinations, not QA worker write permissions. Accepted milestone entry for docs/CHANGELOG.md is proposed as a controller report artifact/diff, not silently committed into tested source; any later source integration must preserve renewed revision evidence. No fictitious accepted changelog is written now.

## Acceptance checklist and requirement mapping

- GOV-001/002/004: exact signed approved plan/spec/policy, valid leases and bases; M1-only scope; §14 OPEN decisions handled only before affected work; no automatic M2.
- FND-001: clean frozen workspace, six nonempty real hosted app jobs plus infrastructure checks; trusted bot PR/current-head provenance and combined candidate checks.
- FND-002: tokens/themes/translations, all labels/errors/mail/a11y keyed; missing-key/pseudolocalization and keyboard/contrast/state tests.
- FND-003/004: full real identity lifecycle, restricted durable schema/migrations, validated session-owned endpoints, shared limits/security; actual staged email and Google/GitHub flows.
- FND-005/006/008: every profile field, skip/edit/conflict/persistence, <60s SHOULD measured, one-action profile link and reserved later continuation.
- FND-007: distinct truthful empty dashboard; no invented ownership/progress/mastery/readiness/content.
- NFR-001/007: applicable ASVS L2 control mapping, cookies/CSRF/CSP/secrets/roles/dependency scans and atomic anti-abuse/failure controls; no unresolved MUST gap.
- NFR-002: WCAG2.2AA and responsive all states, manual keyboard/screen-reader, desktop and physical phone staging, performance trace/profile. Emulation is separate.
- NFR-003/004: export/delete/recent-auth/revocation/consent/retention/restore suppression and safe schema-validated events, docs and redacted telemetry.
- NFR-005: scheduled daily encrypted backups, actual isolated restore, fresh/seeded migration, compatible rollback and fault/alert evidence.
- Specification §15: acceptance, unit/E2E, accessibility, loading/empty/error, docs, events, applicable LATER-disabled flags and phone/desktop staging mapped per feature/exact revision; all MUST evidence present. SHOULD results explicit. No placeholder/live-provider inference.
- CT-01–04: executable controller lifecycle/amendment/provenance/staging regressions pass after prerequisites implemented. Regression proposals are not actual infrastructure success.

## Proposed versus executed evidence

`proposed_tests/` contains executable regression contracts for future infrastructure tasks. The lifecycle test exercises current ledger using only flat implementation items; it is supplemental fixture evidence. Amendment/CI/staging tests deliberately require new APIs; not run/claimed passing before implementation. OPS tasks must port these to their owned automation paths, test actual CLI/authentication/API wiring and obtain independent trusted CI. `validate_plan.py` runs only manifest/path/dependency/digest/ownership checks. `VALIDATION.json` records exactly what this worker ran. No application, hosted CI, staging, live provider or physical device check is claimed by planning submission.

## Runtime escalation and delivery handoff

Commission OPS-101–106 and policy registration in their explicit protected paths after exact plan approval; this planning worker cannot make them executable. Actual staging host/provider/budget prerequisites remain external. If controller ledger already has attempts, replacement graph cannot safely import now; escalate to trusted lead for bounded general amendment support. Do not bypass that mismatch with raw SQL or revise-plan. Publish PR/hash only via trusted controller after review. Production remains unconfigured and excluded; final founder production approval cannot be inferred from plan approval.
