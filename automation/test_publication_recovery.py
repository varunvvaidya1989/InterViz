"""First-source recovery tests: authenticated fixtures and real local Git only."""
import base64
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock,patch

from automation import cli,runtime
from automation.control import Control,ControlError
from automation.recovery import publication_handoff
from automation.test_recovery import archive

PLAN='a'*64
PR='https://github.com/test/repo/pull/71'
REPORT={'summary':'Original retained source','verdict':'SUBMITTED','findings':[],'evidence':['fixture checks'],'limitations':[]}


class FirstPublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'repo';self.root.mkdir();(self.root/'automation').mkdir()
        (self.root/'automation/a.py').write_bytes(b'original\n')
        self.git=runtime.git;self.git(['init','-b','main'],self.root)
        self.commit('base');self.base=self.git(['rev-parse','HEAD'],self.root);self.before=runtime.scan_files(self.root)
        (self.root/'automation/a.py').write_bytes(b'worker proposal\n')
        self.after=runtime.scan_files(self.root);self.changed=runtime.changes(self.before,self.after)
        self.bundle=runtime.source_bundle(self.root,self.before,self.after,self.changed,['automation/'],source={})
        self.commit('retained source');self.head=self.git(['rev-parse','HEAD'],self.root)
        self.git(['checkout','--detach',self.base],self.root)
        self.now=1000.;self.control=Control(Path(self.temp.name)/'state.db',{'founder'},clock=lambda:self.now)
        c=self.control;c.create_release('R-1','Release','lead');c.upsert_story('R-1','S','Story',
           {'allowed_paths':['automation/'],'acceptance':['Outcome'],'role':'devops','kind':'infrastructure'},[],'lead')
        c.submit_plan('R-1',PLAN,'lead');c.approve_plan('R-1',PLAN,'founder')
        self.item=c.claim('R-1','S','original-worker',lease_seconds=60);self.now=1061.
        self.result={'role':'devops','reference':'R-1:story:S','kind':'story','revision':self.base,
                     'worker_id':'original-worker','lease_id':self.item['lease_id'],'plan_hash':PLAN,
                     'baseline':self.before,'after':self.after,'changed_paths':self.changed,
                     'source_bundle':self.bundle,'report':REPORT}
        self.data=archive(self.result)
        self.source={'id':12,'workflow_id':7,'path':'.github/workflows/agent-control.yml','head_branch':'main',
                     'head_sha':self.base,'event':'workflow_dispatch','status':'completed','conclusion':'failure',
                     'repository':{'id':1},'head_repository':{'id':1},'run_attempt':1,
                     'run_started_at':'1970-01-01T00:15:00Z','updated_at':'1970-01-01T00:17:30Z',
                     'html_url':'https://github.com/test/repo/actions/runs/12'}
        self.artifact={'id':20,'name':'sdlc-control-12-1','expired':False,'digest':'sha256:'+hashlib.sha256(self.data).hexdigest(),
                       'created_at':'1970-01-01T00:17:20Z','workflow_run':{'id':12,'repository_id':1,'head_repository_id':1,'head_sha':self.base}}
        self.jobs={'jobs':[{'steps':[{'name':'Execute queued Codex worker through isolated adapter','conclusion':'success'},
                                    {'name':'Reconcile policy and schedule permitted next work','conclusion':'failure'}]}]}
        self.client=MagicMock();self.client.repository='test/repo';self.client.root='/repos/test/repo'
        self.client.info.return_value={'id':1,'default_branch':'main'}
        self.pr={'number':71,'html_url':PR,'state':'open','draft':False,'user':{'login':'founder'},
                 'head':{'sha':self.head,'repo':{'full_name':'test/repo'}},'base':{'ref':'main','repo':{'full_name':'test/repo'}}}
        self.client.pr.side_effect=lambda n:copy.deepcopy(self.pr)
        self.client.pages.return_value=[{'filename':'automation/a.py','status':'modified'}]
        self.client.request.side_effect=self.request
        self.p=copy.deepcopy(cli.policy());self.p['repository']['full_name']='test/repo';self.p['founders']['usernames']=['founder']
        self.args=Namespace(task_id='R-1:story:S',source_run_id=12,pull_request=71,revision=self.head,accept_ci_workflow_blob=None)
        self.values={}

    def commit(self,message):
        self.git(['add','.'],self.root);self.git(['-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m',message],self.root)

    def request(self,method,path,*args):
        if path.endswith('/agent-control.yml'):return {'id':7}
        if path.endswith('/runs/99'):return {'event':'workflow_dispatch','head_branch':'main','path':'.github/workflows/agent-control.yml'}
        if path.endswith('/runs/12'):return self.source
        if path.endswith('/jobs'):return self.jobs
        if path.endswith('/artifacts'):return {'artifacts':[self.artifact]}
        raise AssertionError(path)

    def handoff(self,*args):
        return publication_handoff(*args,download=lambda *a:self.data)

    def boundary(self,args,cwd,**kw):
        if args[0]=='fetch' and args[1].startswith('https://github.com/'):
            args=[args[0],str(self.root),*args[2:]]
        return self.git(args,cwd,**kw)

    def recover(self):
        def kv(key,value=None,write=False):
            if write:self.values[key]=value
            return self.values.get(key)
        with patch.object(cli,'ROOT',self.root),patch.object(cli,'OUT',self.root/'.sdlc/output'),\
             patch.object(cli,'ledger',return_value=self.control),patch.object(cli,'github',return_value=self.client),\
             patch.object(cli,'principal',return_value='founder'),patch.object(cli,'require_current_plan',return_value=({},PLAN)),\
             patch.object(cli,'publication_handoff',side_effect=self.handoff),patch.object(cli,'kv',side_effect=kv),\
             patch.object(cli,'git',side_effect=self.boundary),patch.dict(os.environ,{'GITHUB_RUN_ID':'99'}):
            return cli.recover_publication(self.p,self.args)

    def test_exact_retained_candidate_recovers_once_preserving_attempts_and_authors(self):
        result=self.recover()['result']
        self.assertEqual(result['attempts'],1);self.assertEqual(result['max_attempts'],2)
        self.assertEqual(result['status'],'SUBMITTED');self.assertEqual(result['epoch'],self.item['epoch']+1)
        self.assertEqual(set(result['author_ids']),{'original-worker','founder','github:founder'})
        self.assertIsNone(result['lease_id']);self.assertTrue(self.control.verify_audit()['valid'])
        events=len(self.control.events());self.recover();self.assertEqual(len(self.control.events()),events)
        for author in ['original-worker','founder','github:founder']:
            with self.assertRaises(ControlError):self.control.record_review('R-1','S',self.head,author,'APPROVE',{'fixture':True},author)
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,result)
        self.control.record_review('R-1','S',self.head,'reviewer','APPROVE',{'fixture':True},'reviewer')
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,result)
        self.control.record_ci('R-1','S',self.head,True,{'fixture':True},'ci')
        with self.control._tx(False) as db:self.control._pr_ready(db,result)

    def test_replay_cannot_reopen_rejection_or_change_source(self):
        self.recover();self.args.source_run_id=13
        with self.assertRaises(ValueError):self.recover()
        self.args.source_run_id=12
        self.control.record_review('R-1','S',self.head,'reviewer','REQUEST_CHANGES',{'finding':'defect'},'reviewer')
        with self.assertRaises(ControlError):self.recover()
        self.assertEqual(self.control.snapshot()['items'][0]['attempts'],1)

    def test_source_provenance_worker_and_tree_tampering_fail_closed(self):
        for mode in ['foreign-run','expired-artifact','failed-worker','wrong-worker','wrong-lease','changed-byte','wrong-base','failed-report']:
            with self.subTest(mode=mode):
                source=copy.deepcopy(self.source);artifact=copy.deepcopy(self.artifact);jobs=copy.deepcopy(self.jobs)
                data=self.data;result=copy.deepcopy(self.result);before=self.control.snapshot()
                if mode=='foreign-run':self.source['head_repository']['id']=2
                if mode=='expired-artifact':self.artifact['expired']=True
                if mode=='failed-worker':self.jobs['jobs'][0]['steps'][0]['conclusion']='failure'
                if mode=='wrong-worker':result['worker_id']='other'
                if mode=='wrong-lease':result['lease_id']='other'
                if mode=='changed-byte':
                    result['after']['automation/a.py']=runtime.digest(b'tampered')
                    result['source_bundle']['files']['automation/a.py']=base64.b64encode(b'tampered').decode()
                if mode=='wrong-base':result['revision']=self.head
                if mode=='failed-report':result['report']['verdict']='BLOCKED'
                if mode in ['wrong-worker','wrong-lease','changed-byte','wrong-base','failed-report']:
                    self.data=archive(result);self.artifact['digest']='sha256:'+hashlib.sha256(self.data).hexdigest()
                with self.assertRaises((ValueError,RuntimeError)):self.recover()
                self.assertEqual(self.control.snapshot(),before)
                self.source=source;self.artifact=artifact;self.jobs=jobs;self.data=data

    def test_foreign_or_racing_pr_active_lease_and_wrong_paths_fail_closed(self):
        before=self.control.snapshot()
        self.pr['head']['sha']='f'*40
        with self.assertRaises(ValueError):self.recover()
        self.pr['head']['sha']=self.head;self.now=1000.
        # The CLI checks wall time; the transactional ledger checks its own live clock.
        with self.assertRaises(ControlError):self.recover()
        self.now=1061.;self.client.pages.return_value=[{'filename':'automation/other.py'}]
        with self.assertRaises(ValueError):self.recover()
        self.assertEqual(self.control.snapshot(),before)

    def test_transition_rolls_back_and_cache_replay_does_not_erase_new_evidence(self):
        before=self.control.snapshot()
        with patch.object(self.control,'_event',side_effect=RuntimeError('fixture crash')):
            with self.assertRaises(RuntimeError):self.recover()
        self.assertEqual(self.control.snapshot(),before)
        self.recover();key='reviewed:R-1:story:S:'+self.head
        self.values[key]={'verdict':'APPROVE'};self.recover()
        self.assertEqual(self.values[key],{'verdict':'APPROVE'})

    def test_explicit_workflow_acceptance_is_exact_and_does_not_supply_ci_success(self):
        self.recover();blob='c'*40
        self.control.accept_recovered_ci_workflow('R-1','S',self.head,blob,PLAN,'founder')
        events=self.control.events();receipt=events[-1]['payload']
        self.assertEqual(receipt['workflow_path'],'.github/workflows/infrastructure-ci.yml')
        self.assertEqual(receipt['epoch'],self.control.snapshot()['items'][0]['epoch'])
        self.control.accept_recovered_ci_workflow('R-1','S',self.head,blob,PLAN,'founder')
        self.assertEqual(len(self.control.events()),len(events))
        with self.assertRaises(ControlError):self.control.accept_recovered_ci_workflow('R-1','S','f'*40,blob,PLAN,'founder')
        with self.assertRaises(ControlError):self.control.accept_recovered_ci_workflow('R-1','S',self.head,blob,PLAN,'worker')
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,self.control.snapshot()['items'][0])

    def test_wrong_explicit_workflow_blob_does_not_partially_submit(self):
        before=self.control.snapshot();self.args.accept_ci_workflow_blob='c'*40
        self.client.file.return_value={'sha':'d'*40}
        with self.assertRaisesRegex(ValueError,'does not match'):self.recover()
        self.assertEqual(self.control.snapshot(),before)

    def test_changed_ci_definition_needs_exact_current_receipt_and_failed_run_stays_failed(self):
        self.recover();blob='c'*40
        client=MagicMock();client.repository='test/repo';client.root='/repos/test/repo'
        client.pr.return_value=self.pr;client.info.return_value={'default_branch':'main'}
        client.pages.return_value=[{'filename':'automation/a.py'}]
        client.file.side_effect=lambda path,ref:{'sha':'d'*40 if ref=='main' else blob}
        client.request.return_value={'id':8}
        run={'id':44,'workflow_id':8,'status':'completed','event':'pull_request','head_sha':self.head,
             'pull_requests':[{'number':71}],'conclusion':'failure','html_url':'https://github.com/test/repo/actions/runs/44'}
        with patch.object(cli,'kv',return_value=None),patch.object(cli,'require_current_plan',return_value=({},PLAN)):
            with self.assertRaisesRegex(ValueError,'separate trusted acceptance'):
                cli.record_ci_run(self.p,client,self.control,run)
            self.control.accept_recovered_ci_workflow('R-1','S',self.head,blob,PLAN,'founder')
            actual=self.control.events
            original=actual('R-1')
            for field,value in [('epoch',99),('head_sha','f'*40),('blob_sha','f'*40),('plan_hash','f'*64)]:
                bad=copy.deepcopy(original)
                for event in bad:
                    if event['type']=='recovered_ci_workflow_accepted':event['payload'][field]=value
                with self.subTest(field=field),patch.object(self.control,'events',return_value=bad):
                    with self.assertRaisesRegex(ValueError,'separate trusted acceptance'):
                        cli.record_ci_run(self.p,client,self.control,run)
            cli.record_ci_run(self.p,client,self.control,run)
        with self.control._tx(False) as db:
            rows=list(db.execute('SELECT passed FROM ci_runs'))
        self.assertEqual(len(rows),1);self.assertFalse(rows[0]['passed'])
        calls=client.request.call_args_list
        checks=[c.args[2] for c in calls if c.args[0]=='POST']
        self.assertEqual(checks[-1]['conclusion'],'failure')



class GitDiagnosticsTests(unittest.TestCase):
    def test_only_fixed_labels_escape_failed_git(self):
        for stderr,reason in [('refusing to allow a GitHub App to update workflow with secret-fixture','workflow-write-permission-required'),
                              ('fatal: Authentication failed for https://secret-fixture','authentication-failed'),
                              ('unexpected private output secret-fixture','operation-failed')]:
            result=subprocess.CompletedProcess([],1,stdout='private-fixture',stderr=stderr)
            with patch.object(runtime.subprocess,'run',return_value=result),self.assertRaises(RuntimeError) as caught:
                runtime.git(['push','https://secret-fixture','HEAD:branch'],'fixture',token='private-token')
            self.assertIn('Git push failed ('+reason+')',str(caught.exception))
            for secret in ['secret-fixture','private-fixture','private-token','HEAD:branch']:
                self.assertNotIn(secret,str(caught.exception))

    def test_publish_secret_is_only_mapped_to_reconcile_not_worker_or_ledger_steps(self):
        workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/agent-control.yml').read_text()
        self.assertEqual(workflow.count('secrets.SDLC_PUBLISH_TOKEN'),1)
        reconcile=workflow.split('      - name: Reconcile policy and schedule permitted next work')[1].split('      - name:')[0]
        self.assertIn('SDLC_PUBLISH_TOKEN: ${{ secrets.SDLC_PUBLISH_TOKEN }}',reconcile)


if __name__=='__main__':unittest.main()
