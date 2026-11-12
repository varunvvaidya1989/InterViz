"""OPS-102 regression using synthetic ledgers and authenticated API fixtures only."""
import copy
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation import cli
from automation.control import Control, ControlError

P='a'*64
H='b'*40


class AmendmentCLI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'planning').mkdir()
        (self.root/'planning/Systems Labs Product Specification.md').write_text('synthetic spec',encoding='utf-8')
        self.c=Control(self.root/'ledger.db',{'founder'})
        self.c.create_release('R1','Fixture','lead')
        for key,deps in [('S1',[]),('S2',['S1'])]:
            self.c.upsert_story('R1',key,key,{'allowed_paths':['automation/'],
                'acceptance':['Original acceptance'],'role':'devops','kind':'infrastructure'},deps,'lead')
        self.c.submit_plan('R1',P,'lead');self.c.approve_plan('R1',P,'founder')
        claim=self.c.claim('R1','S1','coder')
        self.c.associate_pr('R1','S1',H,'https://example.test/1','coder','controller',lease_id=claim['lease_id'])
        self.c.record_review('R1','S1',H,'reviewer','APPROVE',{'fixture':'review'},'reviewer')
        self.c.record_ci('R1','S1',H,True,{'fixture':'CI'},'ci')
        self.c.integrate('R1','S1',H,'c'*40,'controller')
        self.plan=dict(release_id='R1',title='Fixture',user_stories=[
            dict(id=i['id'],title=i['title'],**i['scope'],depends_on=i['depends_on']) for i in self.c.snapshot('R1')['items']],
            ui_ux={'fixture':True},architecture={'fixture':True},operations={'fixture':True},
            acceptance_tests=[{'fixture':True}],delivery_tasks={'fixture':True})
        self.path=self.root/'plan.json';self.write_plan()
        self.p=copy.deepcopy(cli.policy());self.p['founders']['usernames']=['founder']
        self.p['version']='synthetic-new-policy'
        self.store={'plan:R1':{'document':copy.deepcopy(self.plan),'hash':P},
                    'queue:devops:R1:story:S2':{'revision':'c'*40}}
        def kv(key,value=None,write=False):
            if write:self.store[key]=value
            return self.store.get(key)
        self.addCleanup(patch.stopall)
        patch.object(cli,'ROOT',self.root).start();patch.object(cli,'kv',side_effect=kv).start()
        patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}).start()
        self.before=self.c.snapshot('R1')['items']

    def write_plan(self):self.path.write_text(json.dumps(self.plan),encoding='utf-8')

    def amend(self,old=P,actor='founder'):
        return cli.amend_plan(self.p,self.c,self.path,old,actor)

    def worker(self):
        args=Namespace(role='devops',task_id='R1:story:S2',revision='c'*40,event_path=None)
        with patch.object(cli,'ledger',return_value=self.c),patch.object(cli,'git',side_effect=RuntimeError('isolated checkout reached')):
            return cli.worker(self.p,args)

    def api(self):
        client=MagicMock();client.root='/repos/test/repo';client.repository='test/repo'
        client.pages.return_value=[]
        return client

    def reconcile(self,client):
        with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value='founder'), \
             patch.object(cli,'ledger',return_value=self.c),patch.object(cli,'OUT',self.root/'out'), \
             patch.object(cli,'reconcile_pass_aliases'),patch.object(cli,'recover_interrupted',return_value=[]):
            return cli.reconcile(self.p,Namespace())

    def test_policy_drift_blocks_worker_before_claim_and_resumes_only_after_new_approval(self):
        # Executable form of the proposed regression. Infrastructure scope is
        # explicit so the unrelated SaaS-check configuration gate stays intact.
        actual=cli.current_plan(self.p,'R1')[1]
        with self.assertRaisesRegex(ValueError,'approval.*stale'):self.worker()
        self.assertEqual(self.before,self.c.snapshot('R1')['items'])
        self.amend()
        self.assertEqual(self.before,self.c.snapshot('R1')['items'])
        self.assertEqual(self.store['plan:R1']['hash'],actual)
        with self.assertRaisesRegex(ValueError,'approval.*stale'):self.worker()
        with self.assertRaises(ControlError):self.c.approve_plan('R1',P,'founder')
        self.c.approve_plan('R1',actual,'founder')
        with self.assertRaisesRegex(RuntimeError,'isolated checkout reached'):self.worker()
        self.assertEqual(next(i for i in self.c.snapshot('R1')['items'] if i['id']=='S2')['attempts'],1)

    def test_crash_after_ledger_commit_replays_metadata_with_one_audit_event(self):
        original=cli.kv.side_effect
        def interrupted(key,value=None,write=False):
            if write and key=='plan:R1':raise RuntimeError('fixture metadata interruption')
            return original(key,value,write)
        with patch.object(cli,'kv',side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError,'metadata interruption'):self.amend()
        self.assertEqual(self.store['plan:R1']['hash'],P)
        with self.assertRaisesRegex(ValueError,'approval.*stale'):cli.require_current_plan(self.p,self.c,'R1')
        self.amend();self.amend()
        self.assertEqual(len([e for e in self.c.events('R1') if e['type']=='plan_amended']),1)
        self.assertEqual(self.before,self.c.snapshot('R1')['items'])
        self.assertEqual(self.store['queue:devops:R1:story:S2'],{'revision':'c'*40})
        self.assertTrue(self.c.verify_audit()['valid'])

    def test_contract_scope_title_dependency_graph_changes_and_nonfounder_have_no_effect(self):
        for mutation in ('scope','acceptance','title','dependency','deleted','added','actor'):
            with self.subTest(mutation=mutation):
                original=copy.deepcopy(self.plan);before=self.c.snapshot();events=self.c.events();store=copy.deepcopy(self.store)
                story=self.plan['user_stories'][1]
                if mutation=='scope':story['allowed_paths']=['apps/']
                elif mutation=='acceptance':story['acceptance']=['Different']
                elif mutation=='title':story['title']='Changed'
                elif mutation=='dependency':story['depends_on']=[]
                elif mutation=='deleted':self.plan['user_stories'].pop()
                elif mutation=='added':self.plan['user_stories'].append({**story,'id':'S3'})
                self.write_plan()
                with self.assertRaises((ValueError,ControlError)):self.amend(actor='other' if mutation=='actor' else 'founder')
                self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.c.events(),events);self.assertEqual(self.store,store)
                self.plan=original;self.write_plan()

    def test_active_lease_and_stale_cas_reject_without_metadata_changes(self):
        before=copy.deepcopy(self.store)
        with self.assertRaises(ControlError):self.amend(old='d'*64)
        self.assertEqual(self.store,before)
        self.c.claim('R1','S2','live-worker')
        snapshot=self.c.snapshot()
        with self.assertRaises(ControlError):self.amend()
        self.assertEqual(self.store,before);self.assertEqual(self.c.snapshot(),snapshot)

    def test_ordinary_import_event_and_scheduled_replay_cannot_replace_started_plan(self):
        self.c.claim('R1','S2','live-worker')
        before=self.c.snapshot();events=self.c.events();store=copy.deepcopy(self.store)
        client=self.api();comment={'id':20,'body':'/sdlc plan plan.json','user':{'login':'founder'}}
        path=self.root/'event.json';path.write_text(json.dumps({'comment':comment}),encoding='utf-8')
        with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value='founder'),patch.object(cli,'ledger',return_value=self.c):
            with self.assertRaisesRegex(ValueError,'Started releases require amend-plan'):
                cli.event(self.p,Namespace(event_name='issue_comment',event_path=str(path)))
        client.pages.side_effect=lambda url,**kwargs:[comment] if url.endswith('/issues/comments') else []
        self.reconcile(client)
        self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.c.events(),events);self.assertEqual(self.store,store)
        client.dispatch.assert_not_called();client.pr.assert_not_called()

    def test_identical_started_import_replay_preserves_active_lease_and_original_metadata(self):
        self.amend();actual=self.store['plan:R1']['hash'];self.c.approve_plan('R1',actual,'founder')
        self.c.claim('R1','S2','live-worker')
        self.store['plan:R1']['pr_url']='fixture://original-provenance'
        before=self.c.snapshot();events=self.c.events();store=copy.deepcopy(self.store)
        result=cli.adopt_plan(self.p,self.c,self.path,'founder')
        self.assertEqual(result['plan_hash'],actual)
        self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.c.events(),events);self.assertEqual(self.store,store)

    def test_reconcile_drift_does_not_dispatch_merge_or_schedule_qa(self):
        client=self.api();events=self.c.events();before=copy.deepcopy(self.store)
        self.reconcile(client)
        client.dispatch.assert_not_called();client.pr.assert_not_called();client.create_issue.assert_not_called()
        client.request.assert_not_called()
        self.assertEqual(self.c.events(),events);self.assertEqual(self.store,before)
        self.amend();self.reconcile(client);client.dispatch.assert_not_called()
        actual=self.store['plan:R1']['hash'];self.c.approve_plan('R1',actual,'founder')
        self.store['queue:devops:R1:story:S2']=None
        client.create_issue.return_value={'number':1};client.info.return_value={'default_branch':'main'}
        client.request.return_value={'object':{'sha':'c'*40}}
        self.reconcile(client);client.dispatch.assert_called_once()

    def test_stale_submitted_result_is_not_published_or_integrated(self):
        out=self.root/'out';out.mkdir()
        (out/'worker-result.json').write_text(json.dumps({'role':'review','kind':'story','reference':'R1:story:S1',
            'revision':H,'report':{'verdict':'APPROVE'},'worker_id':'reviewer'}),encoding='utf-8')
        before=self.c.snapshot();events=self.c.events();client=self.api()
        with patch.object(cli,'OUT',out):
            with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value='founder'),patch.object(cli,'ledger',return_value=self.c):
                with self.assertRaisesRegex(ValueError,'approval.*stale'):cli.reconcile(self.p,Namespace())
        client.request.assert_not_called();self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.c.events(),events)

    def submit_second(self):
        claim=self.c.claim('R1','S2','second-coder')
        self.c.associate_pr('R1','S2','d'*40,'https://example.test/2','second-coder','controller',lease_id=claim['lease_id'])
        self.c.record_review('R1','S2','d'*40,'independent','APPROVE',{'fixture':'review'},'independent')
        self.c.record_ci('R1','S2','d'*40,True,{'fixture':'CI'},'ci')

    def test_stale_plan_blocks_otherwise_ready_founder_merge_reconciliation(self):
        self.submit_second();before=self.c.snapshot();events=self.c.events();client=self.api()
        client.pr.return_value={'merged':True,'merged_by':{'login':'founder'},'merge_commit_sha':'e'*40}
        self.reconcile(client)
        client.pr.assert_not_called();self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.c.events(),events)

    def test_stale_plan_blocks_qa_when_every_story_is_integrated_and_staging_configured(self):
        self.submit_second();self.c.integrate('R1','S2','d'*40,'e'*40,'controller')
        self.p['checks']['application_configured']=True
        self.p['environment']['staging']['configured']=True
        before=self.c.snapshot();events=self.c.events();client=self.api()
        self.reconcile(client)
        client.dispatch.assert_not_called();self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.c.events(),events)

    def test_candidate_and_publication_reject_stale_plan_before_effects(self):
        client=self.api();before=self.c.snapshot()
        for phase in ('candidate','publish'):
            with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value='founder'),patch.object(cli,'ledger',return_value=self.c):
                with self.assertRaisesRegex(ValueError,'approval.*stale'):
                    cli.release(self.p,Namespace(candidate_id='R1',revision=H,phase=phase))
        client.request.assert_not_called();self.assertEqual(self.c.snapshot(),before)

    def test_authenticated_event_and_scheduled_replay_share_idempotent_amendment(self):
        client=self.api();comment={'id':12,'body':'/sdlc amend-plan R1 plan.json '+P,'user':{'login':'founder'}}
        path=self.root/'event.json';path.write_text(json.dumps({'comment':comment}),encoding='utf-8')
        with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value='founder'),patch.object(cli,'ledger',return_value=self.c):
            cli.event(self.p,Namespace(event_name='issue_comment',event_path=str(path)))
        self.store.pop('comment:12') # emulate receipt save interruption, not a ledger reset
        def pages(url,**kwargs):return [comment] if url.endswith('/issues/comments') else []
        client.pages.side_effect=pages
        self.reconcile(client)
        self.assertTrue(self.store['comment:12']['processed'])
        self.assertEqual(len([e for e in self.c.events('R1') if e['type']=='plan_amended']),1)
        self.assertEqual(self.c.snapshot('R1')['items'],self.before)

    def test_wrong_actor_or_release_event_does_not_mutate_state(self):
        before=self.c.snapshot();store=copy.deepcopy(self.store);client=self.api()
        for actor,release in [('outsider','R1'),('founder','WRONG')]:
            comment={'id':13,'body':'/sdlc amend-plan '+release+' plan.json '+P,'user':{'login':actor}}
            path=self.root/'event.json';path.write_text(json.dumps({'comment':comment}),encoding='utf-8')
            with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value=actor),patch.object(cli,'ledger',return_value=self.c):
                with self.assertRaises(ValueError):cli.event(self.p,Namespace(event_name='issue_comment',event_path=str(path)))
            self.assertEqual(self.c.snapshot(),before);self.assertEqual(self.store,store)

    def test_hosted_amendment_uses_committed_bytes_and_rejects_untracked_or_modified_inputs(self):
        (self.root/'automation').mkdir();(self.root/'automation/policy.json').write_text(json.dumps(self.p),encoding='utf-8')
        cli.git(['init'],self.root);cli.git(['add','.'],self.root)
        cli.git(['-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m','trusted fixture'],self.root)
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}):
            self.assertEqual(cli.amendment_document(self.p,self.path)[0],self.plan)
            self.plan['operations']={'changed':True};self.write_plan()
            with self.assertRaisesRegex(ValueError,'differ from'):self.amend()
            self.plan['operations']={'fixture':True};self.write_plan()
            other=self.root/'untracked.json';other.write_text(json.dumps(self.plan),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'trusted committed'):cli.amendment_document(self.p,other)
        self.assertEqual(self.c.snapshot('R1')['items'],self.before)


if __name__=='__main__':unittest.main()
