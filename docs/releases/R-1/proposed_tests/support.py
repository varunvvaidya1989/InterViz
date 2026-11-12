"""Synthetic, local-only ledger fixture; no remote API or credentials."""
import tempfile
import unittest
from pathlib import Path
from automation.control import Control, ControlError

P = 'a' * 64
H = 'b' * 40
C = 'c' * 40
N = 'd' * 40
E = {'artifact': 'fixture://R-1', 'result': 'PASS'}

class LedgerCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.control = Control(Path(temp.name) / 'ledger.db', founder_ids=['founder'])
        self.control.create_release('R1', 'M1 fixture', 'lead')
        scope = {'allowed_paths': ['apps/web/'], 'acceptance': ['Owner boundary works']}
        self.control.upsert_story('R1', 'S1', 'Identity slice', scope, [], 'lead')
        self.control.upsert_story('R1', 'S2', 'Dashboard slice', scope, ['S1'], 'lead')
        self.control.submit_plan('R1', P, 'lead')
        self.control.approve_plan('R1', P, 'founder')

    def rejected(self, code, fn, *args, **kwargs):
        with self.assertRaises(ControlError) as caught:
            fn(*args, **kwargs)
        self.assertEqual(code, caught.exception.code)

    def submit(self, item, head, kind='story', author='coder'):
        lease = self.control.claim('R1', item, author, kind=kind)
        self.control.associate_pr('R1', item, head, 'https://example.test/' + item,
                                  author, 'github-service', kind=kind,
                                  lease_id=lease['lease_id'])

    def review(self, item, head, kind='story'):
        self.control.record_review('R1', item, head, 'reviewer', 'APPROVE', E,
                                   'reviewer', kind=kind)

    def integrate(self, item, head, candidate, kind='story'):
        self.submit(item, head, kind)
        self.review(item, head, kind)
        self.control.record_ci('R1', item, head, True, E, 'ci', kind=kind)
        self.control.integrate('R1', item, head, candidate, 'controller', kind=kind)
