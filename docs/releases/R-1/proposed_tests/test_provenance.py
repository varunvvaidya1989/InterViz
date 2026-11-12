"""Proposed OPS-103/105 integration seams, NOT RUN; modules do not exist yet.
Wire actual authenticated API/CLI tests in owned automation tests as well.
"""
import copy
import importlib
from support import LedgerCase, H, C

class ApplicationProvenance(LedgerCase):
    def test_missing_failed_stale_forged_checks_block_then_current_success_permits(self):
        ci = importlib.import_module('automation.ci')
        self.submit('S1', H)
        self.review('S1', H)
        required = [dict(name=name, repository='fixture/repo', pr=1,
                         workflow_id=9, workflow_blob='trusted-blob')
                    for name in ['sdlc-infrastructure-ci', 'application-unit-integration', 'application-e2e']]
        facts = [dict(**entry, head=H, run_id=i+1, attempt=1,
                      status='completed', conclusion='success') for i, entry in enumerate(required)]
        for invalid in [facts[:-1], [dict(f, conclusion='failure') for f in facts],
                        [dict(f, head='d'*40) for f in facts],
                        [dict(f, workflow_id=666) for f in facts]]:
            ci.reconcile_checks(self.control, 'R1', 'S1', H, invalid, required, 'trusted-api')
            self.rejected('ci_required', self.control.integrate, 'R1', 'S1', H, C, 'controller')
        ci.reconcile_checks(self.control, 'R1', 'S1', H, facts, required, 'trusted-api')
        self.control.integrate('R1', 'S1', H, C, 'controller')
        # A later failed rerun revokes previous evidence.
        failed = [dict(f, attempt=2, conclusion='failure') for f in facts]
        ci.reconcile_checks(self.control, 'R1', 'S1', H, failed, required, 'trusted-api')
        self.rejected('ci_required', self.control.integrate, 'R1', 'S1', H, C, 'controller')

    def test_staging_inspects_actual_deployment_before_and_after_remote_checks(self):
        staging = importlib.import_module('automation.staging')
        candidate = dict(commit=C, image_digest='sha256:'+'a'*64, environment_id='staging-1')
        class Transport:
            def __init__(self, receipt): self.receipt = receipt
            def inspect(self): return copy.deepcopy(self.receipt)
            def smoke(self): return {'status': 'PASS', 'environment_id': 'staging-1'}
        receipt = dict(candidate, migration_id='m1-001', url='https://staging.example.test',
                       timestamp='2026-11-10T12:00:00Z', workflow_run_id=123)
        self.assertEqual('PASS', staging.validate_candidate(candidate, Transport(receipt))['status'])
        for patch in [dict(commit=H), dict(image_digest='sha256:'+'b'*64),
                      dict(environment_id='other'), dict(workflow_run_id=None)]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                staging.validate_candidate(candidate, Transport(dict(receipt, **patch)))
        class ChangedDuringChecks(Transport):
            def smoke(self):
                self.receipt['commit'] = H
                return {'status': 'PASS', 'environment_id': 'staging-1'}
        with self.assertRaises(ValueError):
            staging.validate_candidate(candidate, ChangedDuringChecks(copy.deepcopy(receipt)))
