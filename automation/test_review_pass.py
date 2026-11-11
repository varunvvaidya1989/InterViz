"""A real PASS is positive review evidence; unavailable/failing evidence is not."""
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import MagicMock,patch

from automation import cli
from automation.control import Control
from automation.providers import REVIEW_CONTRACT
from automation.recovery import verified_pass_report

PLAN='a'*64
HEAD='b'*40
PASS={'summary':'PASS exact candidate','verdict':'PASS','findings':[],'evidence':['all fixture tests passed'],'limitations':[]}


class ReviewPassTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.c=Control(Path(self.temp.name)/'state.db',{'founder'})
        c=self.c;c.create_release('R','Release','lead');c.upsert_story('R','S','Story',{'allowed_paths':['automation/'],'acceptance':['Outcome']},[],'lead')
        c.submit_plan('R',PLAN,'lead');c.approve_plan('R',PLAN,'founder')
        lease=c.claim('R','S','coder');c.associate_pr('R','S',HEAD,'https://github.com/test/repo/pull/51','coder','controller',lease_id=lease['lease_id'])
        self.client=MagicMock();self.client.root='/repos/test/repo';self.client.repository='test/repo'
        self.client.pr.return_value={'state':'open','head':{'sha':HEAD,'repo':{'full_name':'test/repo'}}}
        self.values={'worker-attempt:review:R:story:S:'+HEAD:2,'worker-attempt:review:R:story:S:'+HEAD+':'+REVIEW_CONTRACT:2}
    def kv(self,key,value=None,write=False):
        if write:self.values[key]=value
        return self.values.get(key)

    def result(self,report=PASS):
        return {'role':'review','reference':'R:story:S','revision':HEAD,'worker_id':'independent',
                'review_contract':REVIEW_CONTRACT,'plan_hash':PLAN,'changed_paths':[],
                'baseline':{'automation/file.py':'c'*64},'after':{'automation/file.py':'c'*64},'report':report}

    def test_live_pass_is_approved_but_blocking_findings_still_reject(self):
        for report,expected in [(PASS,'APPROVE'),({**PASS,'findings':[{'id':'bug','severity':'high','description':'Bug','reproduction':'fixture'}]},'REQUEST_CHANGES')]:
            with self.subTest(expected=expected):
                out=Path(self.temp.name)/'output';out.mkdir(exist_ok=True)
                (out/'worker-result.json').write_text(json.dumps(self.result(report)))
                with patch.object(cli,'OUT',out),patch.object(cli,'kv',side_effect=self.kv):
                    cli.publish_result(cli.policy(),self.client,self.c)
                with self.c._tx(False) as db:
                    row=db.execute('SELECT verdict,evidence FROM reviews ORDER BY seq DESC LIMIT 1').fetchone()
                    self.assertEqual(row['verdict'],expected);self.assertEqual(json.loads(row['evidence'])['report']['verdict'],'PASS')

    def positive_event(self):
        self.c.record_review_environment('R','S',HEAD,'independent',{'report':PASS,'execution':'12','contract':REVIEW_CONTRACT},'independent')
        return self.c.events()[-1]

    def test_replay_preserves_source_and_recovers_check_cache_after_interruption(self):
        source=self.positive_event();evidence={'report':PASS,'execution':'12','contract':REVIEW_CONTRACT,
                   'verdict_alias':'PASS','source_environment_event':source['seq'],'url':'https://github.com/test/repo/actions/runs/12'}
        before={k:v for k,v in self.values.items()}
        def interrupted(key,value=None,write=False):
            if write:raise RuntimeError('fixture interruption')
            return self.kv(key,value,write)
        with patch.object(cli,'current_plan',return_value=({},PLAN)),patch.object(cli,'pr_files',return_value=([],[])), \
             patch.object(cli,'verified_pass_report',return_value=dict(evidence)),patch.object(cli,'kv',side_effect=interrupted):
            with self.assertRaises(RuntimeError):cli.reconcile_pass_aliases(cli.policy(),self.client,self.c)
        with patch.object(cli,'kv',side_effect=self.kv):
            cli.reconcile_pass_aliases(cli.policy(),self.client,self.c)
            cli.reconcile_pass_aliases(cli.policy(),self.client,self.c)
        with self.c._tx(False) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM reviews').fetchone()[0],1)
            row=db.execute('SELECT reviewer_id,verdict,evidence FROM reviews').fetchone()
            self.assertEqual(row['reviewer_id'],'independent');self.assertEqual(row['verdict'],'APPROVE')
            self.assertEqual(json.loads(row['evidence'])['report'],PASS)
        for key,value in before.items():self.assertEqual(self.values[key],value)
        self.assertIsNone(self.values['ci-queued:'+HEAD])
        self.assertTrue(self.c.verify_audit()['valid'])
        self.assertEqual(self.client.request.call_count,1)

    def test_later_real_rejection_or_new_submission_cannot_inherit_old_pass(self):
        self.positive_event()
        self.c.record_review('R','S',HEAD,'other','REQUEST_CHANGES',{'actual':'code bug'},'other')
        for mode in ('rejected','resubmitted'):
            with self.subTest(mode=mode),patch.object(cli,'verified_pass_report') as verify:
                if mode=='resubmitted':
                    lease=self.c.claim('R','S','coder2')
                    self.c.associate_pr('R','S',HEAD,'https://github.com/test/repo/pull/51','coder2','controller',lease_id=lease['lease_id'])
                cli.reconcile_pass_aliases(cli.policy(),self.client,self.c)
                verify.assert_not_called()

    def test_retained_positive_requires_matching_run_digest_identity_plan_and_report(self):
        event=self.positive_event();item=self.c.snapshot()['items'][0]
        data=io.BytesIO()
        with zipfile.ZipFile(data,'w') as z:z.writestr('worker-result.json',json.dumps(self.result()))
        blob=data.getvalue();artifact={'id':20,'name':'sdlc-control-12-1','expired':False,
            'digest':'sha256:'+hashlib.sha256(blob).hexdigest(),'workflow_run':{'id':12,'head_sha':'d'*40,'repository_id':1,'head_repository_id':1}}
        run={'id':12,'workflow_id':7,'path':'.github/workflows/agent-control.yml','head_branch':'main','event':'workflow_dispatch',
             'status':'completed','conclusion':'success','repository':{'id':1},'head_repository':{'id':1},'run_attempt':1,'head_sha':'d'*40,'html_url':'https://github.com/test/repo/actions/runs/12'}
        self.client.info.return_value={'id':1,'default_branch':'main'}
        def request(method,path):
            if path.endswith('/agent-control.yml'):return {'id':7}
            if path.endswith('/12'):return run
            if path.endswith('/artifacts'):return {'artifacts':[artifact]}
            raise AssertionError(path)
        self.client.request.side_effect=request
        result=verified_pass_report(self.client,event,item,PLAN,REVIEW_CONTRACT,download=lambda *args:blob)
        self.assertEqual(result['verdict_alias'],'PASS')
        for field,value in [('plan_hash','e'*64),('review_contract','other'),('worker_id','other')]:
            bad={**self.result(),field:value};stream=io.BytesIO()
            with zipfile.ZipFile(stream,'w') as z:z.writestr('worker-result.json',json.dumps(bad))
            bad_blob=stream.getvalue();artifact['digest']='sha256:'+hashlib.sha256(bad_blob).hexdigest()
            with self.subTest(field=field),self.assertRaises(ValueError):
                verified_pass_report(self.client,event,item,PLAN,REVIEW_CONTRACT,download=lambda *args:bad_blob)
