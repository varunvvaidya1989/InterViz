"""Correct review environment failure without fabricating code acceptance."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock,patch

from automation import cli
from automation.control import Control,ControlError
from automation.providers import DockerAgent,REVIEW_CONTRACT

PLAN='a'*64
HEAD='b'*40
BLOCKED={'summary':'Fixtures unavailable','verdict':'BLOCKED','findings':[],'evidence':['no writable temp'],'limitations':['tests not completed']}


class ReviewEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.c=Control(Path(self.temp.name)/'state.db',{'founder'})
        c=self.c;c.create_release('R','Release','lead')
        c.upsert_story('R','S','Story',{'allowed_paths':['automation/'],'acceptance':['Outcome']},[],'lead')
        c.submit_plan('R',PLAN,'lead');c.approve_plan('R',PLAN,'founder')
        lease=c.claim('R','S','coder');c.associate_pr('R','S',HEAD,'https://github.com/test/repo/pull/51','coder','controller',lease_id=lease['lease_id'])

    def reject(self,report=None):
        self.c.record_review('R','S',HEAD,'old-reviewer','REQUEST_CHANGES',{'report':report or BLOCKED},'old-reviewer')

    def test_corrected_contract_reopens_only_empty_blocked_review_preserving_history(self):
        self.reject();before=self.c.snapshot()['items'][0];events=len(self.c.events())
        after=self.c.reopen_blocked_review('R','S',HEAD,REVIEW_CONTRACT,'controller')
        self.assertEqual(after['status'],'SUBMITTED');self.assertEqual(after['epoch'],before['epoch']+1)
        self.assertEqual(after['attempts'],before['attempts']);self.assertEqual(len(self.c.events()),events+1)
        with self.c._tx(False) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0],1)
            with self.assertRaises(ControlError):self.c._pr_ready(db,after)
        self.assertTrue(self.c.verify_audit()['valid'])

    def test_genuine_findings_cannot_be_reopened_as_environment_failure(self):
        findings=[{'id':'bug','severity':'high','description':'Actual bug','reproduction':'fixture'}]
        self.reject({**BLOCKED,'findings':findings})
        before=self.c.snapshot()
        with self.assertRaises(ControlError):self.c.reopen_blocked_review('R','S',HEAD,REVIEW_CONTRACT,'controller')
        self.assertEqual(self.c.snapshot(),before)

    def test_same_contract_cannot_repeatedly_reopen_or_clear_new_rejections(self):
        self.reject();self.c.reopen_blocked_review('R','S',HEAD,REVIEW_CONTRACT,'controller')
        self.c.record_review('R','S',HEAD,'new-reviewer','REQUEST_CHANGES',{'report':BLOCKED},'new-reviewer')
        with self.assertRaises(ControlError):self.c.reopen_blocked_review('R','S',HEAD,REVIEW_CONTRACT,'controller')

    def test_environment_failure_stays_submitted_and_invalidates_acceptance(self):
        c=self.c;c.record_review('R','S',HEAD,'reviewer','APPROVE',{'fixture':'review'},'reviewer')
        c.record_ci('R','S',HEAD,True,{'fixture':'CI'},'ci')
        before=c.snapshot()['items'][0]
        after=c.record_review_environment('R','S',HEAD,'other-reviewer',{'report':BLOCKED},'other-reviewer')
        self.assertEqual(after['status'],'SUBMITTED');self.assertEqual(after['attempts'],before['attempts'])
        with c._tx(False) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0],1)
            with self.assertRaises(ControlError):c._pr_ready(db,after)
        self.assertEqual(c.events()[-1]['type'],'review_environment_blocked')

    def test_publisher_does_not_convert_blocked_execution_into_code_rejection(self):
        out=Path(self.temp.name)/'output';out.mkdir()
        result={'role':'review','reference':'R:story:S','report':BLOCKED,'revision':HEAD,
                'worker_id':'independent-review','review_contract':REVIEW_CONTRACT}
        (out/'worker-result.json').write_text(json.dumps(result))
        client=MagicMock();client.root='/repos/test/repo';values={}
        def kv(key,value=None,write=False):
            if write:values[key]=value
            return values.get(key)
        with patch.object(cli,'OUT',out),patch.object(cli,'kv',side_effect=kv):
            processed=cli.publish_result(cli.policy(),client,self.c)
        self.assertTrue(processed['environment_blocked'])
        self.assertEqual(self.c.snapshot()['items'][0]['status'],'SUBMITTED')
        with self.c._tx(False) as db:self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0],0)
        self.assertEqual(client.request.call_args.args[2]['conclusion'],'failure')

    def test_fixture_probe_before_model_receives_no_api_key(self):
        calls=[]
        def runner(command,**kwargs):
            import subprocess
            calls.append((command,kwargs))
            return subprocess.CompletedProcess(command,1,'','fixture probe failed')
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fixture-secret'}):
            with self.assertRaises(RuntimeError):DockerAgent(runner=runner).run(self.temp.name,'review','codex','fixture')
        self.assertEqual(len(calls),1)
        self.assertIn('CREATE TABLE probe',calls[0][0][-1]);self.assertNotIn('OPENAI_API_KEY',calls[0][1]['env'])
        self.assertNotIn('CODEX_API_KEY',calls[0][1]['env'])
