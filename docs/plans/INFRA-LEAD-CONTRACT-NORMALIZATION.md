# Lead submission contract normalization

12 November 2026. Hosted adoption run43163537908 rejected OPS102 before mutation.
The signed approved manifest lists the original three paths in a different order
from Control._scope's stored sorted set. Independent local inspection confirms
normalized scope, title and dependencies match exactly. The old single-path test
fixture did not exercise this difference.

Bounded lead correction: automation/cli.py uses the existing ledger scope
normalizer before comparing the approved manifest with the stored contract.
automation/test_lead_rework.py uses the actual three-path ordering and verifies
reordered identical paths pass while additions/removals still reject without any
state, audit or metadata mutation. No task, scope, attempt, authority, approved
plan hash, review or CI evidence is changed by this repair. Original task attempts
remain2/2. This correction does not waive the failed preflight.

Run the infrastructure suite, policy validation and independent exact-commit
review plus hosted CI. Protected founder acceptance is required before installing
the new controller revision. Existing authorizations for task63 and dashboard64
remain bound to their original candidates and checks; retry the same adopted
submission only after this controller correction is accepted.
