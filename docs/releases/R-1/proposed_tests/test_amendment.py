"""Proposed OPS-101 API contract; NOT RUN until amend_plan is implemented.
OPS-102 additionally tests canonical hash, authenticated CLI and dispatch barriers.
"""
from support import LedgerCase, H, P, E

class PolicyAmendment(LedgerCase):
    def test_resubmit_preserves_work_counters_audit_and_requires_fresh_approval(self):
        self.integrate('S1', H, 'c' * 40)
        before = self.control.snapshot('R1')
        events = self.control.events('R1')
        new = 'f' * 64  # CLI computes real new canonical plan/spec/policy hash.
        self.rejected('founder_required', self.control.amend_plan,
                      'R1', P, new, 'worker')
        self.control.amend_plan('R1', P, new, 'founder')
        after = self.control.snapshot('R1')
        self.assertEqual(before['items'], after['items'])
        self.assertEqual(events, self.control.events('R1')[:len(events)])
        self.assertEqual(new, after['releases'][0]['plan_hash'])
        self.assertEqual(before['releases'][0]['integration_sha'], after['releases'][0]['integration_sha'])
        self.assertIsNone(after['releases'][0]['plan_approved_hash'])
        self.rejected('plan_not_approved', self.control.claim, 'R1', 'S2', 'coder')
        self.rejected('stale_plan', self.control.approve_plan, 'R1', P, 'founder')
        # Same amendment retry is idempotent, never resets attempts.
        count = len(self.control.events('R1'))
        self.control.amend_plan('R1', P, new, 'founder')
        self.assertEqual(count, len(self.control.events('R1')))
        self.control.approve_plan('R1', new, 'founder')
        lease = self.control.claim('R1', 'S2', 'coder')
        self.assertEqual(1, lease['attempts'])
        self.assertTrue(self.control.verify_audit()['valid'])

    def test_no_amendment_during_active_lease(self):
        self.control.claim('R1', 'S1', 'coder')
        before = self.control.snapshot('R1')
        self.rejected('lease_active', self.control.amend_plan, 'R1', P, 'f' * 64, 'founder')
        self.assertEqual(before, self.control.snapshot('R1'))
