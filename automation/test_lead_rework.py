"""Bounded founder-authenticated lead correction fixtures; no remote mutations."""
import copy
import json
import os
import tempfile
import unittest
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation import cli
from automation.control import Control, ControlError
from automation.runtime import digest

PLAN='a'*64
HEAD='b'*40
PR='https://github.com/test/repo/pull/60'
CONTRACT='OPS102-LEAD-v1'
REWORK_CONTRACT='OPS102-REPLAY-v1'
CORRECTED='c'*40
SCOPE={'allowed_paths':['automation/cli.py','automation/test_amendment_cli.py','automation/README.md'],
       'acceptance':['Preserve exact plan authority.'],'role':'devops','kind':'infrastructure'}


class LeadReworkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1000.0;self.path=Path(self.temp.name)/'state.db'
        self.control=Control(self.path,{'founder'},clock=lambda:self.now)
        c=self.control;c.create_release('R-1','Release','lead')
        c.upsert_story('R-1','D','Dependency',{**SCOPE,'allowed_paths':['automation/dependency.py']},[],'lead')
        c.upsert_story('R-1','S','Lead correction',SCOPE,['D'],'lead')
        c.submit_plan('R-1',PLAN,'lead');c.approve_plan('R-1',PLAN,'founder')
        lease=c.claim('R-1','D','dependency-coder',lease_seconds=10)
        c.associate_pr('R-1','D','d'*40,'https://github.com/test/repo/pull/59','dependency-coder','controller',lease_id=lease['lease_id'])
        c.record_review('R-1','D','d'*40,'dependency-review','APPROVE',{'fixture':'review'},'dependency-review')
        c.record_ci('R-1','D','d'*40,True,{'fixture':'CI'},'ci')
        c.integrate('R-1','D','d'*40,'e'*40,'integrator')
        c.claim('R-1','S','first-worker',lease_seconds=10);self.now+=11
        self.claim=c.claim('R-1','S','second-worker',lease_seconds=10);self.now+=11

    def tables(self):
        with self.control._tx(False) as db:
            return {table:[dict(row) for row in db.execute('SELECT * FROM '+table)]
                    for table in ('releases','items','reviews','ci_runs','approvals','events','release_records')}

    def adopt(self,**changes):
        values={'release_id':'R-1','item_id':'S','head_sha':HEAD,'pr_url':PR,'author_id':'founder',
                'plan_hash':PLAN,'contract':CONTRACT,'evidence':{'execution':123,'concrete_pr':60},'actor':'founder'}
        return self.control.adopt_lead_submission(**{**values,**changes})

    def assertRejected(self,code,**changes):
        before=self.tables()
        with self.assertRaises(ControlError) as caught:self.adopt(**changes)
        self.assertEqual(caught.exception.code,code)
        self.assertEqual(self.tables(),before)

    def test_exhausted_attempts_and_history_survive_new_unapproved_submission(self):
        before=self.tables();old=self.claim
        item=self.adopt();after=self.tables()
        self.assertEqual(item['status'],'SUBMITTED');self.assertEqual(item['attempts'],2)
        self.assertEqual(item['max_attempts'],2);self.assertEqual(item['epoch'],old['epoch']+1)
        self.assertEqual(item['developer_id'],'founder')
        self.assertEqual(set(item['author_ids']),{'first-worker','second-worker','founder'})
        self.assertIsNone(item['lease_id']);self.assertIsNone(item['lease_worker']);self.assertIsNone(item['lease_until'])
        for table in ('reviews','ci_runs','approvals','release_records'):
            self.assertEqual(after[table],before[table])
        self.assertEqual(after['events'][:-1],before['events'])
        audit=json.loads(after['events'][-1]['payload'])
        self.assertEqual(audit['contract'],CONTRACT);self.assertEqual(audit['plan_hash'],PLAN)
        self.assertEqual(audit['head_sha'],HEAD);self.assertEqual(audit['pr_url'],PR)
        self.assertEqual(audit['attempts'],2);self.assertEqual(audit['submitted_epoch'],item['epoch'])
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,item)
        with self.assertRaises(ControlError):
            self.control.record_review('R-1','S',HEAD,'first-worker','APPROVE',{'fixture':'not independent'},'first-worker')
        self.control.record_review('R-1','S',HEAD,'fresh-review','APPROVE',{'fixture':'review'},'fresh-review')
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,item)
        self.control.record_ci('R-1','S',HEAD,True,{'fixture':'new exact CI'},'ci')
        with self.control._tx(False) as db:self.control._pr_ready(db,item)
        self.assertTrue(self.control.verify_audit()['valid'])

    def test_founder_plan_contract_and_expired_lease_are_mandatory(self):
        self.assertRejected('founder_required',actor='worker')
        self.assertRejected('founder_required',author_id='worker')
        self.assertRejected('stale_plan',plan_hash='f'*64)
        for contract in ('',' ','invalid\ncontract'):
            self.assertRejected('lead_contract_required',contract=contract)
        self.now-=11;self.assertRejected('lease_active');self.now+=11
        with self.control._tx() as db:db.execute("UPDATE items SET attempts=1 WHERE id='S'")
        self.assertRejected('attempts_not_exhausted')

    def test_changed_scope_dependencies_and_previous_submission_are_rejected(self):
        for column,value,code in [('scope',json.dumps({**SCOPE,'allowed_paths':['automation/']}),'stale_plan'),
                                  ('depends_on','[]','stale_plan'),('pr_url',PR,'prior_submission'),
                                  ('head_sha',HEAD,'prior_submission')]:
            with self.subTest(column=column):
                with self.control._tx() as db:
                    original=db.execute('SELECT '+column+" FROM items WHERE id='S'").fetchone()[0]
                    db.execute('UPDATE items SET '+column+"=? WHERE id='S'",(value,))
                self.assertRejected(code)
                with self.control._tx() as db:db.execute('UPDATE items SET '+column+"=? WHERE id='S'",(original,))
        with self.control._tx() as db:db.execute("UPDATE items SET status='OPEN' WHERE id='D'")
        self.assertRejected('dependency_not_ready')
        with self.control._tx() as db:
            db.execute("UPDATE items SET status='INTEGRATED' WHERE id='D'")
            self.control._event(db,'R-1','pr_head_associated','worker',{'kind':'story','item_id':'S','head_sha':'f'*40,'pr_url':PR})
        self.assertRejected('prior_submission')

    def test_another_active_scope_blocks_adoption(self):
        c=self.control;c.create_release('R-2','Other','lead');c.upsert_story('R-2','OTHER','Other',SCOPE,[],'lead')
        c.submit_plan('R-2','c'*64,'lead');c.approve_plan('R-2','c'*64,'founder');c.claim('R-2','OTHER','other-worker',lease_seconds=10)
        self.assertRejected('scope_busy')

    def test_one_adoption_is_idempotent_only_while_same_submission_remains_current(self):
        first=self.adopt();before=self.tables();self.assertEqual(self.adopt(),first);self.assertEqual(self.tables(),before)
        self.assertRejected('lead_rework_already_adopted',head_sha='f'*40)
        self.assertRejected('lead_rework_already_adopted',contract='OPS102-LEAD-v2')
        self.control.record_review('R-1','S',HEAD,'reviewer','REQUEST_CHANGES',{'fixture':'real code issue'},'reviewer')
        self.assertRejected('lead_rework_already_adopted')
        with self.assertRaises(ControlError):self.control.claim('R-1','S','third-worker')

    def test_concurrent_identical_adoption_has_one_audit_effect(self):
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.adopt(),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(sum(e['type']=='lead_submission_adopted' for e in self.control.events()),1)

    def test_audit_failure_rolls_back_candidate_and_does_not_consume_adoption(self):
        before=self.tables()
        with patch.object(self.control,'_event',side_effect=RuntimeError('fixture interrupted audit')):
            with self.assertRaises(RuntimeError):self.adopt()
        self.assertEqual(self.tables(),before)
        self.assertEqual(self.adopt()['status'],'SUBMITTED')

    def test_worker_failure_releases_only_matching_lease_and_preserves_spent_attempts(self):
        before=self.tables()
        with self.assertRaises(ControlError):
            self.control.record_worker_failure('R-1','S','second-worker','wrong',{'fixture':'report'},'second-worker')
        self.assertEqual(self.tables(),before)
        result=self.control.record_worker_failure('R-1','S','second-worker',self.claim['lease_id'],{'fixture':'BLOCKED'},'second-worker')
        self.assertEqual(result['status'],'OPEN');self.assertEqual(result['attempts'],2)
        self.assertIsNone(result['lease_id']);self.assertEqual(result['head_sha'],self.claim['head_sha'])
        self.assertEqual(self.control.events()[-1]['type'],'worker_failed')
        self.assertEqual(self.adopt()['status'],'SUBMITTED')

    def test_worker_failure_audit_is_transactional_and_cannot_release_newer_worker(self):
        before=self.tables()
        with patch.object(self.control,'_event',side_effect=RuntimeError('fixture audit failure')):
            with self.assertRaises(RuntimeError):
                self.control.record_worker_failure('R-1','S','second-worker',self.claim['lease_id'],{'fixture':'BLOCKED'},'second-worker')
        self.assertEqual(self.tables(),before)
        with self.assertRaises(ControlError):
            self.control.record_worker_failure('R-1','S','first-worker',self.claim['lease_id'],{'fixture':'BLOCKED'},'first-worker')
        self.assertEqual(self.tables(),before)


class HostedAdoptionTests(unittest.TestCase):
    # Reuse real domain fixtures while mocking only authenticated GitHub boundaries.
    setUp=LeadReworkTests.setUp
    tables=LeadReworkTests.tables
    adopt=LeadReworkTests.adopt
    def api_fixture(self):
        p=copy.deepcopy(cli.policy());p['repository']['full_name']='test/repo';p['repository']['default_branch']='main';p['founders']['usernames']=['founder']
        client=MagicMock();client.root='/repos/test/repo';client.repository='test/repo'
        run={'id':123,'path':'.github/workflows/agent-control.yml','event':'workflow_dispatch','head_branch':'main'}
        client.request.return_value=run
        pr={'number':60,'html_url':PR,'state':'open','draft':False,'user':{'login':'founder'},
            'head':{'sha':HEAD,'repo':{'full_name':'test/repo'}},'base':{'ref':'main','repo':{'full_name':'test/repo'}},'changed_files':1}
        client.pr.return_value=pr;client.pages.return_value=[{'filename':'automation/cli.py','status':'modified','patch':'fixture'}]
        args=Namespace(task_id='R-1:story:S',revision=HEAD,pull_request=60,plan_hash=PLAN,lead_contract=CONTRACT)
        manifest={'document':{'user_stories':[{'id':'S','title':'Lead correction',**SCOPE,'depends_on':['D']}]}}
        values={}
        def kv(key,value=None,write=False):
            if write:values[key]=value
            return values.get(key)
        return p,client,args,manifest,values,kv

    def execute(self,client=None,args=None,manifest=None,actor='founder'):
        p,default_client,default_args,default_manifest,values,kv=self.api_fixture()
        client=client or default_client;args=args or default_args;manifest=manifest or default_manifest
        with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value=actor),\
             patch.object(cli,'ledger',return_value=self.control),patch.object(cli,'current_plan',return_value=(manifest,PLAN)),\
             patch.object(cli,'kv',side_effect=kv),patch.object(cli,'output',side_effect=lambda name,value:value),\
             patch.dict(os.environ,{'GITHUB_RUN_ID':'123'}):
            return cli.adopt_submission(p,args),values

    def test_hosted_adoption_verifies_original_contract_pr_and_audit_then_only_submits(self):
        result,values=self.execute()
        self.assertEqual(result['status'],'SUBMITTED')
        self.assertEqual(result['result']['attempts'],2)
        self.assertIn('protected:'+PR,values)
        self.assertIsNone(values['ci-queued:'+HEAD])
        self.assertIsNone(values['reviewed:R-1:story:S:'+HEAD])
        self.assertTrue(any(k.startswith('lead-adoption-cache-done:') for k in values))

    def test_manifest_path_order_uses_ledger_normalization_without_scope_expansion(self):
        _,client,args,manifest,_,_=self.api_fixture()
        paths=manifest['document']['user_stories'][0]['allowed_paths']
        stored=next(i for i in self.control.snapshot('R-1')['items'] if i['id']=='S')['scope']['allowed_paths']
        self.assertNotEqual(paths,stored)
        before=self.tables()
        for changed in (paths+['automation/policy.json'],paths[:-1]):
            candidate=copy.deepcopy(manifest);candidate['document']['user_stories'][0]['allowed_paths']=changed
            with self.assertRaisesRegex(ValueError,'original approved task contract'):
                self.execute(client,args,candidate)
            self.assertEqual(self.tables(),before)
        result,_=self.execute(client,args,manifest)
        self.assertEqual(result['status'],'SUBMITTED');self.assertEqual(result['result']['attempts'],2)
        self.assertEqual(result['result']['scope']['allowed_paths'],stored)
        self.assertTrue(self.control.verify_audit()['valid'])

    def test_nonfounder_stale_revision_wrong_repository_author_base_and_files_rejected(self):
        cases=[('head',{'sha':'f'*40,'repo':{'full_name':'test/repo'}}),
               ('head',{'sha':HEAD,'repo':{'full_name':'attacker/fork'}}),
               ('user',{'login':'worker'}),('base',{'ref':'other','repo':{'full_name':'test/repo'}}),
               ('base',{'ref':'main','repo':{'full_name':'attacker/fork'}}),('state','closed'),('draft',True)]
        for field,value in cases:
            with self.subTest(field=field,value=value):
                _,client,args,manifest,_,_=self.api_fixture();client.pr.return_value[field]=value
                before=self.tables()
                with self.assertRaises(ValueError):self.execute(client,args,manifest)
                self.assertEqual(self.tables(),before)
        with self.assertRaises(ValueError):self.execute(actor='worker')
        _,client,args,manifest,_,_=self.api_fixture();args.plan_hash='f'*64
        with self.assertRaises(ValueError):self.execute(client,args,manifest)
        for file in ({'filename':'automation/policy.json','status':'modified'},
                     {'filename':'automation/cli.py','previous_filename':'automation/policy.json','status':'renamed'}):
            _,client,args,manifest,_,_=self.api_fixture();client.pages.return_value=[file]
            with self.assertRaises(ValueError):self.execute(client,args,manifest)
        _,client,args,manifest,_,_=self.api_fixture();client.pr.return_value['changed_files']=2
        with self.assertRaises(ValueError):self.execute(client,args,manifest)

    def test_wrong_workflow_branch_changed_scope_and_midcheck_head_change_fail_closed(self):
        for change in ({'event':'push'},{'head_branch':'feature'},{'path':'.github/workflows/other.yml'}):
            _,client,args,manifest,_,_=self.api_fixture();client.request.return_value.update(change)
            with self.assertRaises(ValueError):self.execute(client,args,manifest)
        _,client,args,manifest,_,_=self.api_fixture();manifest['document']['user_stories'][0]['acceptance']=['Different outcome']
        with self.assertRaises(ValueError):self.execute(client,args,manifest)
        _,client,args,manifest,_,_=self.api_fixture();first=copy.deepcopy(client.pr.return_value);second=copy.deepcopy(first);second['head']['sha']='f'*40;client.pr.side_effect=[first,second]
        with self.assertRaises(ValueError):self.execute(client,args,manifest)

    def test_recovery_cache_replay_is_durable_but_does_not_erase_new_review(self):
        self.adopt();_,_,_,_,values,kv=self.api_fixture()
        with patch.object(cli,'kv',side_effect=kv):
            cli.finish_recovery_cache(self.control)
            values['reviewed:R-1:story:S:'+HEAD]={'verdict':'APPROVE'}
            values['ci-queued:'+HEAD]={'run':456}
            cli.finish_recovery_cache(self.control)
            self.assertEqual(values['reviewed:R-1:story:S:'+HEAD],{'verdict':'APPROVE'})
            self.assertEqual(values['ci-queued:'+HEAD],{'run':456})


class LeadResubmissionTests(unittest.TestCase):
    setUp=LeadReworkTests.setUp
    tables=LeadReworkTests.tables
    adopt=LeadReworkTests.adopt

    def rejected(self,report=None):
        original=self.adopt()
        self.control.record_ci('R-1','S',HEAD,True,{'fixture':'first-head CI'},'ci')
        report=report or {'verdict':'REQUEST_CHANGES','findings':[{'severity':'high','description':'Replay order loses the retained handoff.'}]}
        self.control.record_review('R-1','S',HEAD,'independent-first-review','REQUEST_CHANGES',
                                   {'report':report},'independent-first-review')
        return original

    def resubmit(self,**changes):
        values={'release_id':'R-1','item_id':'S','head_sha':CORRECTED,'pr_url':PR,'author_id':'founder',
                'plan_hash':PLAN,'contract':REWORK_CONTRACT,'evidence':{'execution':456,'concrete_pr':60},'actor':'founder'}
        return self.control.resubmit_lead_submission(**{**values,**changes})

    def assertRejected(self,code,**changes):
        before=self.tables()
        with self.assertRaises(ControlError) as caught:self.resubmit(**changes)
        self.assertEqual(caught.exception.code,code)
        self.assertEqual(self.tables(),before)

    def test_second_head_preserves_real_rejection_and_spent_attempts_requires_new_checks(self):
        original=self.rejected();before=self.tables();item=self.resubmit();after=self.tables()
        self.assertEqual(item['status'],'SUBMITTED');self.assertEqual(item['head_sha'],CORRECTED)
        self.assertEqual((item['attempts'],item['max_attempts']),(2,2))
        self.assertEqual(item['epoch'],original['epoch']+1)
        self.assertEqual(set(item['author_ids']),{'first-worker','second-worker','founder'})
        for table in ('reviews','ci_runs','approvals','release_records'):
            self.assertEqual(after[table],before[table])
        self.assertEqual(after['events'][:-1],before['events'])
        event=self.control.events()[-1]
        self.assertEqual(event['type'],'lead_submission_resubmitted')
        self.assertEqual(event['payload']['source_head_sha'],HEAD)
        self.assertEqual(event['payload']['head_sha'],CORRECTED)
        self.assertEqual(event['payload']['contract'],REWORK_CONTRACT)
        self.assertEqual(event['payload']['previous_contract'],CONTRACT)
        self.assertEqual(event['payload']['attempts'],2)
        self.assertEqual(event['payload']['submitted_epoch'],item['epoch'])
        self.assertEqual(event['payload']['rejection_seq'],before['reviews'][-1]['seq'])
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,item)
        self.control.record_review('R-1','S',CORRECTED,'second-independent-review','APPROVE',{'fixture':'new review'},'second-independent-review')
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,item)
        self.control.record_ci('R-1','S',CORRECTED,True,{'fixture':'new exact CI'},'ci')
        with self.control._tx(False) as db:self.control._pr_ready(db,item)
        self.assertTrue(self.control.verify_audit()['valid'])

    def test_second_head_replay_is_read_only_and_cannot_reopen_later_rejection_or_third_head(self):
        self.rejected();first=self.resubmit();before=self.tables()
        self.assertEqual(self.resubmit(),first);self.assertEqual(self.tables(),before)
        self.assertRejected('lead_rework_exhausted',head_sha='f'*40,contract='OPS102-THIRD-v1')
        self.control.record_review('R-1','S',CORRECTED,'second-review','REQUEST_CHANGES',{'actual':'unresolved code issue'},'second-review')
        self.assertRejected('lead_rework_exhausted')
        self.assertRejected('lead_rework_exhausted',head_sha='f'*40,contract='OPS102-THIRD-v1')
        with self.assertRaises(ControlError):self.control.claim('R-1','S','third-coder')

    def test_founder_original_pr_plan_and_new_contract_are_mandatory(self):
        self.rejected()
        self.assertRejected('founder_required',actor='worker')
        self.assertRejected('founder_required',author_id='worker')
        self.assertRejected('lead_contract_changed',pr_url='https://github.com/test/repo/pull/61')
        self.assertRejected('stale_plan',plan_hash='f'*64)
        self.assertRejected('new_rework_required',head_sha=HEAD)
        self.assertRejected('new_rework_required',contract=CONTRACT)
        self.assertRejected('lead_contract_required',contract='')

    def test_only_actual_current_epoch_code_rejection_enables_correction(self):
        self.adopt();self.assertRejected('rejected_submission_required')
        self.control.record_review('R-1','S',HEAD,'environment-review','REQUEST_CHANGES',
                                   {'report':{'verdict':'BLOCKED','findings':[]}},'environment-review')
        self.assertRejected('code_rejection_required')
        self.control.record_review('R-1','S',HEAD,'actual-review','REQUEST_CHANGES',{'actual':'code defect'},'actual-review')
        with self.control._tx() as db:db.execute("UPDATE items SET epoch=epoch+1 WHERE id='S'")
        self.assertRejected('code_rejection_required')

    def test_active_lease_scope_dependency_and_attempt_changes_fail_closed(self):
        self.rejected()
        for column,value,code in [('lease_until',self.now+10,'lease_active'),
                                  ('scope',json.dumps({**SCOPE,'allowed_paths':['automation/']}),'stale_plan'),
                                  ('depends_on','[]','stale_plan'),('attempts',1,'attempts_changed')]:
            with self.subTest(column=column):
                with self.control._tx() as db:
                    original=db.execute('SELECT '+column+" FROM items WHERE id='S'").fetchone()[0]
                    db.execute('UPDATE items SET '+column+"=? WHERE id='S'",(value,))
                self.assertRejected(code)
                with self.control._tx() as db:db.execute('UPDATE items SET '+column+"=? WHERE id='S'",(original,))
        with self.control._tx() as db:db.execute("UPDATE items SET status='OPEN' WHERE id='D'")
        self.assertRejected('dependency_not_ready')
        with self.control._tx() as db:db.execute("UPDATE items SET status='INTEGRATED' WHERE id='D'")
        c=self.control;c.create_release('R-2','Other','lead');c.upsert_story('R-2','OTHER','Other',SCOPE,[],'lead')
        c.submit_plan('R-2','c'*64,'lead');c.approve_plan('R-2','c'*64,'founder');c.claim('R-2','OTHER','other-worker',lease_seconds=10)
        self.assertRejected('scope_busy')

    def test_resubmission_audit_failure_rolls_back_head_epoch_and_contract_consumption(self):
        self.rejected();before=self.tables()
        with patch.object(self.control,'_event',side_effect=RuntimeError('fixture audit interrupted')):
            with self.assertRaises(RuntimeError):self.resubmit()
        self.assertEqual(self.tables(),before)
        self.assertEqual(self.resubmit()['status'],'SUBMITTED')

    def test_concurrent_duplicate_correction_has_one_effect_and_competing_head_is_rejected(self):
        self.rejected()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.resubmit(),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(sum(e['type']=='lead_submission_resubmitted' for e in self.control.events()),1)
        self.assertRejected('lead_rework_exhausted',head_sha='f'*40,contract='COMPETING-v1')


class HostedResubmissionTests(unittest.TestCase):
    setUp=LeadReworkTests.setUp
    tables=LeadReworkTests.tables
    adopt=LeadReworkTests.adopt
    api_fixture=HostedAdoptionTests.api_fixture
    execute=HostedAdoptionTests.execute
    rejected=LeadResubmissionTests.rejected

    def test_hosted_action_routes_new_contract_to_the_same_pr_second_head_only(self):
        self.rejected();p,client,args,manifest,_,_=self.api_fixture()
        args.revision=CORRECTED;args.lead_contract=REWORK_CONTRACT
        client.pr.return_value['head']['sha']=CORRECTED
        result,values=self.execute(client,args,manifest)
        self.assertEqual(result['result']['head_sha'],CORRECTED)
        self.assertEqual(result['result']['attempts'],2)
        self.assertFalse(any(key.startswith('worker-attempt:') for key in values))
        self.assertEqual(self.control.events()[-1]['type'],'lead_submission_resubmitted')
        result,_=self.execute(client,args,manifest)
        self.assertEqual(result['status'],'SUBMITTED')

    def test_corrective_remote_checks_reject_changed_pr_nonfounder_and_out_of_scope_rename(self):
        self.rejected()
        for mode in ('different-pr','author','rename','plan','actor'):
            with self.subTest(mode=mode):
                _,client,args,manifest,_,_=self.api_fixture()
                args.revision=CORRECTED;args.lead_contract=REWORK_CONTRACT
                client.pr.return_value['head']['sha']=CORRECTED
                if mode=='different-pr':
                    args.pull_request=61;client.pr.return_value.update(number=61,html_url='https://github.com/test/repo/pull/61')
                if mode=='author':client.pr.return_value['user']['login']='worker'
                if mode=='rename':client.pages.return_value=[{'filename':'automation/cli.py','previous_filename':'automation/policy.json','status':'renamed'}]
                if mode=='plan':args.plan_hash='f'*64
                before=self.tables()
                with self.assertRaises((ControlError,ValueError)):
                    self.execute(client,args,manifest,actor='worker' if mode=='actor' else 'founder')
                self.assertEqual(self.tables(),before)


if __name__=='__main__':unittest.main()
