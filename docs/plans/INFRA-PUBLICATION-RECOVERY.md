# Recoverable same-PR publication and bounded OPS-103 lead takeover

12 November 2026. Founder-directed recovery; infrastructure only. Trusted main
base `6413653642584a9eca313bb8bed2f76f78bad089`. One writer in isolated branch
`fix/publication-recovery`, worktree `.sdlc/worktrees/publication-recovery`, owns
`automation/cli.py`, `automation/control.py`, `automation/runtime.py`, new
publication/takeover tests and this plan. Root implements the actual OPS-103
semantic CI correction on its separate original three-path task branch.

The second automated OPS-103 worker returned SUBMITTED with changes, but publisher
checkout failed because its trusted shallow clone lacked the exact worker base.
The existing publisher also proposed another PR despite a fixed task PR identity.
Retained run 43176862787/artifact 13925035449 has hashes/report only: it cannot
restore the lost source bytes and does not prove any manually recreated source.
Preserve both spent attempts, all original review findings and the interrupted
lease. Never describe the historical lost code as recovered.

## Support changes

- Fetch and verify a missing exact base in the clean trusted publisher clone.
  Never execute worker-mutated Git metadata.
- Rework updates the existing same-repository open task PR's original branch with
  a descendant commit through non-forced fast-forward publication. Revalidate
  exact prior head, base, complete scope and current head; reject closure, forks,
  races or changed scope. Associate the same PR in a fresh transactional epoch.
- Capture bounded credential-checked changed-file bytes and explicit deletions in
  the worker result before publication. Verify maps, allowlist, hash and size;
  never retain credentials, raw provider output or arbitrary workspace archives.
  Historical results without bytes remain unavailable if their workspace is gone.
- Existing founder-hosted adoption may take over only an exhausted, expired,
  interrupted rework of its proven original bot-authored PR, under explicit
  `OPS103-LEAD-v1`. Require same approved normalized scope/dependencies, exact PR
  and concrete new head, no active/overlapping lease and original association/
  current claim proof. Record source head/lease/worker in the lead-adoption audit.
  Preserve attempts and all author identities; require fresh actual review/CI.
- Keep initial unsubmitted adoption and its one corrective-head resubmission cap.
  A bot PR exception is restricted to signed prior task/lead-takeover provenance.

## Verification

Real shallow-Git publication fixtures, missing fetch and racing/closed/fork PRs;
bounded source bytes/deletion/hash/credential rejection; existing bot PR identity,
historical proof, active lease, scope/dependencies and transaction rollback tests.
Run all automation tests, infrastructure validation and whitespace checks. Exact
support source requires independent QA, hosted CI and founder acceptance before
protected integration. No remote merge/adoption or production changes in this task.

## Local verification evidence

All 141 automation tests passed, including real shallow-clone/same-PR publication,
worker result source retention before a simulated fetch failure, credential and
bundle cap/hash/deletion checks, and the expired bot-PR takeover lifecycle.
Infrastructure contract validation and whitespace checks passed. Retained source
is capped at 100 changed paths and 2,000,000 decoded bytes per handoff; oversized
or credential-bearing handoffs fail closed with sanitized failure evidence.
These are local fixtures, not a recovered copy of the historical lost worker
source or hosted acceptance of the corrected OPS-103 implementation.
