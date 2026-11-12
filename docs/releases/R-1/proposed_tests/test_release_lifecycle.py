"""Runnable current ledger regression; OPS-106 must also cover CLI scheduling."""
import json
from pathlib import Path
from support import LedgerCase, H, C, N, E

class ReleaseLifecycle(LedgerCase):
    def test_flat_implementation_failed_qa_bug_fix_fresh_qa_acceptance(self):
        manifest = json.loads((Path(__file__).parents[1] / 'plan.json').read_text())
        self.assertFalse(any(s['role'] == 'qa' for s in manifest['user_stories']))
        self.assertTrue(all(not s['ledger_item'] for s in manifest['delivery_tasks']['release_stages']))
        self.integrate('S1', H, '1' * 40)
        self.integrate('S2', '2' * 40, C)
        # No final acceptance story exists to block this call.
        self.control.start_qa('R1', C, 'controller:qa')
        self.rejected('qa_required', self.control.freeze_candidate, 'R1', C, 'lead')
        self.control.create_bug('R1', 'B1', 'Cross-user profile access', 'qa',
                                story_id='S1', severity='high')
        self.rejected('unfinished_items', self.control.start_qa, 'R1', C, 'controller:qa')
        self.submit('B1', N, 'bug')
        self.rejected('self_review', self.control.record_review, 'R1', 'B1', N,
                      'coder', 'APPROVE', E, 'coder', kind='bug')
        self.rejected('review_required', self.control.integrate, 'R1', 'B1', N,
                      'e' * 40, 'controller', kind='bug')
        self.review('B1', N, 'bug')
        self.rejected('ci_required', self.control.integrate, 'R1', 'B1', N,
                      'e' * 40, 'controller', kind='bug')
        self.control.record_ci('R1', 'B1', N, True, E, 'ci', kind='bug')
        fresh = 'e' * 40
        self.control.integrate('R1', 'B1', N, fresh, 'controller', kind='bug')
        self.rejected('stale_candidate', self.control.complete_qa, 'R1', C, E, 'qa')
        self.control.start_qa('R1', fresh, 'controller:qa')
        self.rejected('qa_required', self.control.freeze_candidate, 'R1', fresh, 'lead')
        self.rejected('self_qa', self.control.complete_qa, 'R1', fresh, E, 'coder')
        self.control.complete_qa('R1', fresh, E, 'independent-qa')
        self.control.freeze_candidate('R1', fresh, 'lead')
        release = self.control.snapshot('R1')['releases'][0]
        self.assertTrue(release['qa_passed'])
        self.assertEqual(fresh, release['qa_sha'])
        self.assertIsNone(release['release_approved_sha'])
        self.assertTrue(self.control.verify_audit()['valid'])
