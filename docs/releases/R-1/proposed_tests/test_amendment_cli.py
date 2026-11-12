"""Proposed OPS-102 executable CLI regression. NOT RUN; helper absent today.
Only synthetic temp files/ledger and patched storage; never remote GitHub.
"""
import copy
import json
from pathlib import Path
from unittest.mock import patch
from automation import cli
from support import LedgerCase, H, P

class AmendmentCLI(LedgerCase):
    def test_policy_drift_resubmission_and_approval_control_worker_preflight(self):
        self.integrate('S1', H, 'c'*40)
        before = self.control.snapshot('R1')['items']
        original = cli.policy()
        changed = copy.deepcopy(original)
        changed['version'] = 'fixture-new-policy'
        # A simple identical item-contract document with all controller sections.
        items = self.control.snapshot('R1')['items']
        plan = dict(release_id='R1', title='M1 fixture', user_stories=[
            dict(id=i['id'], title=i['title'], **i['scope'], depends_on=i['depends_on'])
            for i in items], ui_ux={'fixture':True}, architecture={'fixture':True},
            operations={'fixture':True}, acceptance_tests=[{'fixture':True}],
            delivery_tasks={'fixture':True})
        # Use independent temp directory because Control path attribute is private.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'planning').mkdir()
            (root/'planning/Systems Labs Product Specification.md').write_text('synthetic spec')
            path = root/'plan.json'
            path.write_text(json.dumps(plan))
            store = {'plan:R1': {'document':plan, 'hash':P},
                     'queue:coding:R1:story:S2': {'revision':'c'*40}}
            def kv(key, value=None, write=False):
                if write: store[key] = value
                return store.get(key)
            with patch.object(cli, 'ROOT', root), patch.object(cli, 'kv', side_effect=kv):
                _, current = cli.current_plan(changed, 'R1')
                self.assertNotEqual(P, current)
                # worker preflight and reconcile must check equality before effects.
                def dispatch_eligible():
                    release = self.control.snapshot('R1')['releases'][0]
                    return release['plan_hash'] == release['plan_approved_hash'] == cli.current_plan(changed,'R1')[1]
                self.assertFalse(dispatch_eligible())
                from types import SimpleNamespace
                args = SimpleNamespace(role='coding', task_id='R1:story:S2', revision='c'*40, event_path=None)
                def run_worker():
                    with patch.object(cli,'require_live'), patch.object(cli,'ledger',return_value=self.control), patch.object(cli,'git',side_effect=RuntimeError('reached isolated checkout')):
                        return cli.worker(changed,args)
                with self.assertRaisesRegex(ValueError,'approval.*stale'):
                    run_worker()
                self.assertEqual(before,self.control.snapshot('R1')['items'])
                cli.amend_plan(changed, self.control, path, P, 'founder')
                self.assertEqual(before, self.control.snapshot('R1')['items'])
                self.assertEqual(current, store['plan:R1']['hash'])
                self.assertFalse(dispatch_eligible())
                with self.assertRaisesRegex(ValueError,'approval.*stale'):
                    run_worker()
                self.rejected('stale_plan', self.control.approve_plan,'R1',P,'founder')
                self.control.approve_plan('R1',current,'founder')
                self.assertTrue(dispatch_eligible())
                with self.assertRaisesRegex(RuntimeError,'reached isolated checkout'):
                    run_worker()
                pending = next(i for i in self.control.snapshot('R1')['items'] if i['id']=='S2')
                self.assertEqual(1,pending['attempts'])
