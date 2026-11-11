"""Publication recovery fixtures; no live approval or controller-state mutation."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import MagicMock,patch

from automation import cli
from automation.control import Control,ControlError
from automation.recovery import ArtifactRedirect,read_result,source_handoff,unchanged_result
from automation.runtime import git,scan_files

PLAN='a'*64
HEAD='b'*40
PR='https://github.com/test/repo/pull/51'
REPORT={'summary':'No changes necessary','verdict':'SUBMITTED','findings':[],'evidence':['fixture checks'],'limitations':[]}
SCOPE={'allowed_paths':['automation/'],'acceptance':['Outcome'],'role':'devops','kind':'infrastructure'}


def archive(result):
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('worker-result.json',json.dumps(result))
    return data.getvalue()


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1000.0
        self.control=Control(Path(self.temp.name)/'state.db',{'founder'},clock=lambda:self.now)
        c=self.control;c.create_release('R-1','Release','lead');c.upsert_story('R-1','S1','Story',SCOPE,[],'lead')
        c.submit_plan('R-1',PLAN,'lead');c.approve_plan('R-1',PLAN,'founder')
        lease=c.claim('R-1','S1','first',lease_seconds=60)
        c.associate_pr('R-1','S1',HEAD,PR,'first','controller',lease_id=lease['lease_id'])
        c.record_review('R-1','S1',HEAD,'reviewer','REQUEST_CHANGES',{'reason':'checkout unavailable'},'reviewer')
        c.record_ci('R-1','S1',HEAD,False,{'reason':'approval waiting'},'ci')
        self.item=c.claim('R-1','S1','second',lease_seconds=60)
        self.result={'role':'devops','reference':'R-1:story:S1','kind':'story','revision':HEAD,
                     'worker_id':'second','lease_id':self.item['lease_id'],'plan_hash':PLAN,
                     'baseline':{'automation/a.py':'c'*64},'after':{'automation/a.py':'c'*64},
                     'changed_paths':[],'report':copy.deepcopy(REPORT)}
        self.source={'run_id':12,'artifact_id':20,'artifact_digest':'sha256:fixture'}

    def restore(self,**changes):
        values={'release_id':'R-1','item_id':'S1','head_sha':HEAD,'pr_url':PR,'worker_id':'second',
                'lease_id':self.item['lease_id'],'plan_hash':PLAN,'evidence':self.source,'actor':'controller:recovery'}
        return self.control.recover_submission(**{**values,**changes})

    def test_restore_preserves_limits_history_and_requires_fresh_epoch_evidence(self):
        self.now=1061
        with self.control._tx(False) as db:
            old_reviews=[tuple(r) for r in db.execute('SELECT * FROM reviews')]
            old_ci=[tuple(r) for r in db.execute('SELECT * FROM ci_runs')]
        restored=self.restore()
        self.assertEqual(restored['status'],'SUBMITTED');self.assertEqual(restored['attempts'],2)
        self.assertEqual(restored['max_attempts'],2);self.assertEqual(restored['epoch'],self.item['epoch']+1)
        self.assertIsNone(restored['lease_id']);self.assertEqual(set(restored['author_ids']),{'first','second'})
        self.assertEqual(self.control.snapshot('R-1')['releases'][0]['plan_approved_hash'],PLAN)
        with self.control._tx(False) as db:
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM reviews')],old_reviews)
            self.assertEqual([tuple(r) for r in db.execute('SELECT * FROM ci_runs')],old_ci)
            with self.assertRaises(ControlError):self.control._pr_ready(db,restored)
        self.control.record_review('R-1','S1',HEAD,'fresh-reviewer','APPROVE',{'fixture':'new review'},'fresh-reviewer')
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,restored)
        self.control.record_ci('R-1','S1',HEAD,True,{'fixture':'new CI'},'ci')
        with self.control._tx(False) as db:self.control._pr_ready(db,restored)
        self.assertTrue(self.control.verify_audit()['valid'])

    def test_active_lease_wrong_plan_worker_lease_or_candidate_fail_closed(self):
        for change in ({},{'plan_hash':'d'*64},{'worker_id':'other'},{'lease_id':'other'},
                       {'head_sha':'d'*40},{'pr_url':'https://github.com/test/repo/pull/99'}):
            with self.subTest(change=change):
                self.now=1000 if not change else 1061
                before=self.control.snapshot()
                with self.assertRaises(ControlError):self.restore(**change)
                self.assertEqual(self.control.snapshot(),before)
        self.now=1000
        with self.assertRaises(ControlError):self.restore(live_worker=True,actor='different-worker')

    def test_restore_is_idempotent_but_cannot_erase_a_new_rejection(self):
        self.now=1061;self.restore();count=len(self.control.events());self.restore()
        self.assertEqual(len(self.control.events()),count)
        self.control.record_review('R-1','S1',HEAD,'fresh','REQUEST_CHANGES',{'actual':'defect'},'fresh')
        with self.assertRaises(ControlError):self.restore()
        with self.assertRaises(ControlError):self.control.claim('R-1','S1','third')

    def test_restore_rolls_back_if_audit_write_fails(self):
        self.now=1061;before=self.control.snapshot()
        with patch.object(self.control,'_event',side_effect=RuntimeError('fixture interruption')):
            with self.assertRaises(RuntimeError):self.restore()
        self.assertEqual(self.control.snapshot(),before);self.assertTrue(self.control.verify_audit()['valid'])

    def test_unchanged_handoff_rejects_modified_or_unrelated_results(self):
        self.assertEqual(unchanged_result(self.result,self.item,PLAN),self.result)
        for field,value in [('changed_paths',['automation/a.py']),('after',{}),('worker_id','other'),
                            ('lease_id','other'),('plan_hash','d'*64),('role','coding'),
                            ('reference','R-1:story:OTHER'),('report',{**REPORT,'verdict':'BLOCKED'})]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                unchanged_result({**self.result,field:value},self.item,PLAN)

    def source_fixture(self):
        data=archive(self.result)
        client=MagicMock();client.root='/repos/test/repo';client.info.return_value={'id':1,'default_branch':'main'}
        run={'id':12,'workflow_id':7,'path':'.github/workflows/agent-control.yml','head_branch':'main',
             'head_sha':'e'*40,'event':'workflow_dispatch','status':'completed','conclusion':'failure',
             'repository':{'id':1},'head_repository':{'id':1},'run_attempt':1,
             'run_started_at':'1970-01-01T00:15:00Z','updated_at':'1970-01-01T00:17:30Z','html_url':'https://github.com/test/repo/actions/runs/12'}
        artifact={'id':20,'name':'sdlc-control-12-1','expired':False,'digest':'sha256:'+hashlib.sha256(data).hexdigest(),
                  'created_at':'1970-01-01T00:17:20Z','workflow_run':{'id':12,'repository_id':1,'head_repository_id':1,'head_sha':'e'*40}}
        jobs={'jobs':[{'steps':[{'name':'Execute queued Codex worker through isolated adapter','conclusion':'success'},
                               {'name':'Reconcile policy and schedule permitted next work','conclusion':'failure'}]}]}
        def request(method,path):
            if path.endswith('/agent-control.yml'):return {'id':7}
            if path.endswith('/jobs'):return jobs
            if path.endswith('/artifacts'):return {'artifacts':[artifact]}
            raise AssertionError(path)
        client.request.side_effect=request
        return client,run,artifact,data,jobs

    def test_hosted_provenance_digest_and_lease_timing_are_required(self):
        client,run,artifact,data,jobs=self.source_fixture()
        result,source=source_handoff(client,run,self.item,PLAN,download=lambda *args:data)
        self.assertEqual(result,self.result);self.assertEqual(source['run_id'],12)
        for changes in ({'head_branch':'other'},{'workflow_id':99},{'head_repository':{'id':2}},
                        {'updated_at':'1970-01-01T01:00:00Z'},{'conclusion':'success'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                source_handoff(client,{**run,**changes},self.item,PLAN,download=lambda *args:data)
        artifact['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError):source_handoff(client,run,self.item,PLAN,download=lambda *args:data)

    def test_artifact_expiration_wrong_run_and_failed_worker_never_restore(self):
        for mode in ('expired','wrong-run','failed-worker','changed-result'):
            with self.subTest(mode=mode):
                client,run,artifact,data,jobs=self.source_fixture()
                if mode=='expired':artifact['expired']=True
                if mode=='wrong-run':artifact['workflow_run']['id']=99
                if mode=='failed-worker':jobs['jobs'][0]['steps'][0]['conclusion']='failure'
                if mode=='changed-result':
                    data=archive({**self.result,'changed_paths':['automation/a.py']})
                    artifact['digest']='sha256:'+hashlib.sha256(data).hexdigest()
                with self.assertRaises(ValueError):source_handoff(client,run,self.item,PLAN,download=lambda *args:data)

    def test_artifact_download_redirect_strips_github_auth_and_rejects_other_hosts(self):
        handler=ArtifactRedirect();req=urllib.request.Request('https://api.github.com/repos/test/repo/actions/artifacts/20/zip',headers={'Authorization':'Bearer fixture'})
        redirected=handler.redirect_request(req,None,302,'Found',{},'https://results.blob.core.windows.net/fixture')
        self.assertFalse(redirected.has_header('Authorization'))
        for target in ['http://results.blob.core.windows.net/x','https://evil.example/x','https://user:pass@results.blob.core.windows.net/x']:
            with self.assertRaises(ValueError):handler.redirect_request(req,None,302,'Found',{},target)

    def test_cache_recovery_after_interrupted_save_is_repeatable_without_reopening_rejection(self):
        self.now=1061;self.restore();values={'reviewed:R-1:story:S1:'+HEAD:{'verdict':'REQUEST_CHANGES'},'ci-queued:'+HEAD:True}
        def kv(key,value=None,write=False):
            if write:values[key]=value
            return values.get(key)
        with patch.object(cli,'kv',side_effect=kv):
            cli.finish_recovery_cache(self.control)
            self.assertIsNone(values['reviewed:R-1:story:S1:'+HEAD]);self.assertIsNone(values['ci-queued:'+HEAD])
            values['reviewed:R-1:story:S1:'+HEAD]={'verdict':'APPROVE'}
            cli.finish_recovery_cache(self.control)
            self.assertEqual(values['reviewed:R-1:story:S1:'+HEAD],{'verdict':'APPROVE'})

    def test_real_candidate_clone_must_match_retained_bytes_before_restoring_submission(self):
        root=Path(self.temp.name)/'repo';root.mkdir();(root/'automation').mkdir()
        (root/'automation/a.py').write_text('print("fixture")\n')
        git(['init'],root);git(['add','.'],root)
        git(['-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m','candidate'],root)
        head=git(['rev-parse','HEAD'],root);baseline=scan_files(root)
        self.now=1061
        c=self.control;c.create_release('R-2','Second','lead');c.upsert_story('R-2','S2','Other',SCOPE,[],'lead')
        c.submit_plan('R-2',PLAN,'lead');c.approve_plan('R-2',PLAN,'founder')
        first=c.claim('R-2','S2','first',lease_seconds=60)
        c.associate_pr('R-2','S2',head,PR,'first','controller',lease_id=first['lease_id'])
        c.record_review('R-2','S2',head,'reviewer','REQUEST_CHANGES',{'fixture':'checkout'},'reviewer')
        item=c.claim('R-2','S2','second',lease_seconds=60)
        result={**self.result,'reference':'R-2:story:S2','revision':head,'lease_id':item['lease_id'],
                'baseline':baseline,'after':baseline}
        self.now=1122
        client=MagicMock();client.repository='test/repo'
        client.pr.return_value={'html_url':PR,'state':'open','head':{'sha':head,'repo':{'full_name':'test/repo'}},'base':{'ref':'main'}}
        values={}
        def kv(key,value=None,write=False):
            if write:values[key]=value
            return values.get(key)
        with patch.object(cli,'ROOT',root),patch.object(cli,'current_plan',return_value=({},PLAN)), \
             patch.object(cli,'pr_files',return_value=([],[])),patch.object(cli,'kv',side_effect=kv):
            bad={**result,'baseline':{'automation/a.py':'0'*64},'after':{'automation/a.py':'0'*64}}
            with self.assertRaisesRegex(ValueError,'bytes do not match'):
                cli.recover_result({'repository':{'default_branch':'main'}},client,c,item,bad,self.source)
            self.assertEqual(c.snapshot('R-2')['items'][0]['status'],'IN_PROGRESS')
            restored=cli.recover_result({'repository':{'default_branch':'main'}},client,c,item,result,self.source)
            self.assertEqual(restored['status'],'SUBMITTED');self.assertEqual(restored['attempts'],2)
            self.assertTrue(values['recovery-cache-done:'+item['lease_id']])

            # The live path must write the same durable recovery event atomically.
            # Otherwise a crash after SUBMITTED leaves old review receipts stuck.
            c.create_release('R-3','Third','lead');c.upsert_story('R-3','S3','Live',SCOPE,[],'lead')
            c.submit_plan('R-3',PLAN,'lead');c.approve_plan('R-3',PLAN,'founder')
            first=c.claim('R-3','S3','first',lease_seconds=60)
            c.associate_pr('R-3','S3',head,PR,'first','controller',lease_id=first['lease_id'])
            c.record_review('R-3','S3',head,'reviewer','REQUEST_CHANGES',{'fixture':'checkout'},'reviewer')
            live=c.claim('R-3','S3','second',lease_seconds=60)
            live_result={**result,'reference':'R-3:story:S3','lease_id':live['lease_id']}
            key='reviewed:R-3:story:S3:'+head;values[key]={'verdict':'REQUEST_CHANGES'}
            with patch.object(cli,'kv',side_effect=RuntimeError('fixture cache interruption')):
                with self.assertRaisesRegex(RuntimeError,'cache interruption'):
                    cli.recover_result({'repository':{'default_branch':'main'}},client,c,live,live_result)
            self.assertEqual(c.snapshot('R-3')['items'][0]['status'],'SUBMITTED')
            self.assertEqual(values[key],{'verdict':'REQUEST_CHANGES'})
            self.assertTrue(any(e['type']=='submission_recovered' for e in c.events('R-3')))
            cli.finish_recovery_cache(c)
            self.assertIsNone(values[key]);self.assertTrue(values['recovery-cache-done:'+live['lease_id']])
