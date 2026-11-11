import base64
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from automation.control import Control
from automation.github import sign_snapshot
from founder_dashboard.server import classify, read_ledger


class DashboardTests(unittest.TestCase):
    def test_snapshot_is_read_without_mutating_original_and_checksum_is_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            c = Control(Path(directory)/'state.db', founder_ids=['founder'])
            c.create_release('R', 'Release', 'founder')
            import sqlite3
            with closing(sqlite3.connect(Path(directory)/'state.db')) as db:
                db.execute('CREATE TABLE runtime_kv(key TEXT PRIMARY KEY,value TEXT)')
                db.commit()
            blob = c.export_database()
            envelope = sign_snapshot(blob, 'fixture-signing-key-'*3)
            result = read_ledger(envelope)
            self.assertEqual(result['releases'][0]['id'], 'R')
            self.assertEqual(result['verification'], 'github_authenticated_checksum_verified')
            self.assertEqual(c.export_database(), blob)
            wal_header = blob[:18] + b'\x02\x02' + blob[20:]
            self.assertEqual(read_ledger(sign_snapshot(wal_header, 'fixture-signing-key-'*3))['releases'][0]['id'], 'R')
            envelope['sha256'] = '0'*64
            with self.assertRaises(ValueError):
                read_ledger(envelope)

    def test_waiting_is_not_running_or_a_stuck_worker(self):
        release={'plan_hash':'a','plan_approved_hash':'a'}
        item={'status':'OPEN','depends_on':['S1'],'attempts':0,'max_attempts':2,'scope':{'kind':'application'}}
        state,reason=classify(item,release,{'S1':{'status':'OPEN'}})
        self.assertEqual(state,'waiting')
        self.assertIn('S1',reason)

    def test_expired_lease_and_attempt_exhaustion_need_attention(self):
        item={'status':'IN_PROGRESS','lease_until':99,'attempts':1,'max_attempts':2,'scope':{},'depends_on':[]}
        self.assertEqual(classify(item,{}, {},now=100)[0],'blocked')
        item.update(status='OPEN',attempts=2)
        self.assertIn('Attempt limit',classify(item,{}, {})[1])

    def test_review_rejection_and_unapproved_plan_are_not_ready(self):
        item={'status':'OPEN','head_sha':'abc','attempts':1,'max_attempts':2,'scope':{},'depends_on':[]}
        review={'head_sha':'abc','verdict':'REQUEST_CHANGES'}
        self.assertEqual(classify(item,{}, {},review)[0],'rework')
        self.assertEqual(classify(item,{}, {})[0],'blocked')

    def test_integrated_is_separate_from_release_qa(self):
        self.assertEqual(classify({'status':'INTEGRATED'}, {}, {})[0],'integrated')

    def test_recovered_submission_ignores_historical_same_head_rejection(self):
        item={'status':'SUBMITTED','head_sha':'abc','epoch':4,'attempts':2,'max_attempts':2,'scope':{},'depends_on':[]}
        old={'head_sha':'abc','epoch':3,'verdict':'REQUEST_CHANGES'}
        self.assertEqual(classify(item,{}, {},old)[0],'reviewing')
        self.assertEqual(classify(item,{}, {},{**old,'epoch':4})[0],'rework')

    def test_orphaned_lease_is_not_reported_as_an_active_agent(self):
        item={'status':'IN_PROGRESS','lease_until':1000,'updated_at':100}
        self.assertEqual(classify(item,{}, {},now=200,worker_active=False)[0],'blocked')
        self.assertEqual(classify(item,{}, {},now=200,worker_active=True)[0],'running')


if __name__=='__main__':
    unittest.main()
