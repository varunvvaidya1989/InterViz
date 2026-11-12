"""Existing bot-PR takeover fixtures: exact expired claim, no attempt reset."""
import copy
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock,patch

from automation import cli
from automation.control import Control,ControlError

PLAN='a'*64
OLD='b'*40
MANUAL='c'*40
PR='https://github.com/test/repo/pull/68'
SCOPE={'allowed_paths':['automation/cli.py','automation/test_amendment_cli.py','automation/README.md'],
       'acceptance':['Original outcome'],'role':'devops','kind':'infrastructure'}


class TakeoverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.now=1000.;self.control=Control(Path(self.temp.name)/'state.db',{'founder'},clock=lambda:self.now)
        c=self.control;c.create_release('R-1','Release','lead')
        c.upsert_story('R-1','D','Dependency',{**SCOPE,'allowed_paths':['automation/dep.py']},[],'lead')
        c.upsert_story('R-1','S','Interrupted rework',SCOPE,['D'],'lead')
        c.submit_plan('R-1',PLAN,'lead');c.approve_plan('R-1',PLAN,'founder')
        lease=c.claim('R-1','D','dep-worker',lease_seconds=60)
        c.associate_pr('R-1','D','d'*40,'https://github.com/test/repo/pull/1','dep-worker','controller',lease_id=lease['lease_id'])
        c.record_review('R-1','D','d'*40,'dep-review','APPROVE',{'fixture':'review'},'dep-review')
        c.record_ci('R-1','D','d'*40,True,{'fixture':'CI'},'ci');c.integrate('R-1','D','d'*40,'e'*40,'controller')
        first=c.claim('R-1','S','first-worker',lease_seconds=60)
        c.associate_pr('R-1','S',OLD,PR,'first-worker','controller',lease_id=first['lease_id'])
        c.record_review('R-1','S',OLD,'actual-review','REQUEST_CHANGES',{'actual':'CI01/CI02'},'actual-review')
        self.claim=c.claim('R-1','S','second-worker',lease_seconds=60);self.now+=61

    def tables(self):
        with self.control._tx(False) as db:return {t:[dict(r) for r in db.execute('SELECT * FROM '+t)] for t in ('releases','items','reviews','ci_runs','events','approvals')}

    def adopt(self,**changes):
        values={'release_id':'R-1','item_id':'S','head_sha':MANUAL,'pr_url':PR,'author_id':'founder',
                'plan_hash':PLAN,'contract':'OPS103-LEAD-v1','evidence':{'execution':456,'pr_author':'github-actions[bot]'},'actor':'founder'}
        return self.control.adopt_lead_submission(**{**values,**changes})

    def rejected(self,code,**changes):
        before=self.tables()
        with self.assertRaises(ControlError) as caught:self.adopt(**changes)
        self.assertEqual(caught.exception.code,code);self.assertEqual(self.tables(),before)

    def test_expired_existing_bot_pr_takeover_preserves_attempts_authors_history_and_source_proof(self):
        before=self.tables();item=self.adopt();after=self.tables()
        self.assertEqual((item['status'],item['head_sha'],item['pr_url']),('SUBMITTED',MANUAL,PR))
        self.assertEqual((item['attempts'],item['max_attempts']),(2,2));self.assertEqual(item['epoch'],self.claim['epoch']+1)
        self.assertEqual(set(item['author_ids']),{'first-worker','second-worker','founder'});self.assertIsNone(item['lease_id'])
        for table in ('reviews','ci_runs','approvals'):self.assertEqual(after[table],before[table])
        self.assertEqual(after['events'][:-1],before['events'])
        event=self.control.events()[-1]['payload']
        self.assertTrue(event['takeover']);self.assertEqual(event['source_head_sha'],OLD)
        self.assertEqual(event['source_lease_id'],self.claim['lease_id']);self.assertEqual(event['source_worker_id'],'second-worker')
        with self.control._tx(False) as db:
            with self.assertRaises(ControlError):self.control._pr_ready(db,item)
        self.assertEqual(self.adopt(),item);self.assertTrue(self.control.verify_audit()['valid'])

    def test_active_lease_identity_same_head_wrong_pr_and_missing_bot_evidence_fail_closed(self):
        self.now-=61;self.rejected('lease_active');self.now+=61
        self.rejected('founder_required',actor='worker')
        self.rejected('new_lead_head_required',head_sha=OLD)
        self.rejected('prior_submission',pr_url='https://github.com/test/repo/pull/99')
        self.rejected('unproven_submission',evidence={'execution':456,'pr_author':'other-bot'})
        with self.control._tx() as db:db.execute("UPDATE items SET lease_id='unproven-claim' WHERE id='S'")
        self.rejected('unproven_submission')

    def test_changed_scope_dependency_and_overlapping_lease_fail_closed(self):
        with self.control._tx() as db:
            original_scope=db.execute("SELECT scope FROM items WHERE id='S'").fetchone()[0]
            db.execute("UPDATE items SET scope=? WHERE id='S'",('{"allowed_paths":["automation/"],"acceptance":["Different"]}',))
        self.rejected('stale_plan')
        with self.control._tx() as db:
            db.execute("UPDATE items SET scope=? WHERE id='S'",(original_scope,))
            db.execute("UPDATE items SET status='OPEN' WHERE id='D'")
        self.rejected('dependency_not_ready')
        with self.control._tx() as db:db.execute("UPDATE items SET status='INTEGRATED' WHERE id='D'")
        c=self.control;c.create_release('R-2','Other','lead');c.upsert_story('R-2','O','Overlap',SCOPE,[],'lead')
        c.submit_plan('R-2','f'*64,'lead');c.approve_plan('R-2','f'*64,'founder');c.claim('R-2','O','other-worker',lease_seconds=60)
        self.rejected('scope_busy')

    def test_takeover_audit_failure_rolls_back_and_one_corrective_head_cap_survives(self):
        before=self.tables()
        with patch.object(self.control,'_event',side_effect=RuntimeError('fixture interrupted audit')):
            with self.assertRaises(RuntimeError):self.adopt()
        self.assertEqual(self.tables(),before)
        self.adopt();self.control.record_review('R-1','S',MANUAL,'new-review','REQUEST_CHANGES',{'actual':'code issue'},'new-review')
        with self.assertRaises(ControlError):self.adopt()
        new=self.control.resubmit_lead_submission('R-1','S','f'*40,PR,'founder',PLAN,'OPS103-CORRECTION-v1',{'fixture':'new source'},'founder')
        self.assertEqual(new['attempts'],2)
        self.control.record_review('R-1','S','f'*40,'last-review','REQUEST_CHANGES',{'actual':'unresolved'},'last-review')
        with self.assertRaises(ControlError):
            self.control.resubmit_lead_submission('R-1','S','1'*40,PR,'founder',PLAN,'OPS103-THIRD-v1',{'fixture':'forbidden'},'founder')

    def api(self):
        p=copy.deepcopy(cli.policy());p['repository']['full_name']='test/repo';p['repository']['default_branch']='main';p['founders']['usernames']=['founder']
        client=MagicMock();client.root='/repos/test/repo';client.repository='test/repo'
        client.request.return_value={'id':456,'path':'.github/workflows/agent-control.yml','event':'workflow_dispatch','head_branch':'main'}
        client.pr.return_value={'number':68,'html_url':PR,'state':'open','draft':False,'user':{'login':'github-actions[bot]'},
                               'head':{'sha':MANUAL,'repo':{'full_name':'test/repo'}},'base':{'ref':'main','repo':{'full_name':'test/repo'}},'changed_files':1}
        client.pages.return_value=[{'filename':'automation/cli.py','status':'modified','patch':'manual source, not lost worker bytes'}]
        args=Namespace(task_id='R-1:story:S',revision=MANUAL,pull_request=68,plan_hash=PLAN,lead_contract='OPS103-LEAD-v1')
        manifest={'document':{'user_stories':[{'id':'S','title':'Interrupted rework',**SCOPE,'depends_on':['D']}]}}
        return p,client,args,manifest

    def execute(self,client=None,actor='founder'):
        p,default,args,manifest=self.api();client=client or default;values={}
        def kv(key,value=None,write=False):
            if write:values[key]=value
            return values.get(key)
        with patch.object(cli,'github',return_value=client),patch.object(cli,'principal',return_value=actor),\
             patch.object(cli,'ledger',return_value=self.control),patch.object(cli,'current_plan',return_value=(manifest,PLAN)),\
             patch.object(cli,'kv',side_effect=kv),patch.object(cli,'output',side_effect=lambda name,value:value),patch.dict(os.environ,{'GITHUB_RUN_ID':'456'}):
            return cli.adopt_submission(p,args)

    def test_hosted_founder_may_take_over_only_proven_original_bot_pr(self):
        self.assertEqual(self.execute()['result']['head_sha'],MANUAL)
        self.assertTrue(self.control.events()[-1]['payload']['takeover'])

    def test_bot_exception_cannot_authorize_other_actor_pr_or_scope(self):
        _,client,_,_=self.api();before=self.tables()
        with self.assertRaises(ValueError):self.execute(client,actor='worker')
        for mode in ('pr','fork','author','scope'):
            with self.subTest(mode=mode):
                _,client,_,_=self.api()
                if mode=='pr':client.pr.return_value['html_url']='https://github.com/test/repo/pull/99'
                if mode=='fork':client.pr.return_value['head']['repo']['full_name']='attacker/fork'
                if mode=='author':client.pr.return_value['user']['login']='other-bot'
                if mode=='scope':client.pages.return_value=[{'filename':'automation/policy.json'}]
                with self.assertRaises(ValueError):self.execute(client)
                self.assertEqual(self.tables(),before)


if __name__=='__main__':unittest.main()
