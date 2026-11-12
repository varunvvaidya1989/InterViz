"""Real shallow-Git publication and bounded retained-source fixtures only."""
import base64
import copy
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock,patch

from automation import cli,runtime
from automation.control import Control

PLAN='a'*64
REPORT={'summary':'Bounded fixture rework','verdict':'SUBMITTED','findings':[],'evidence':['fixture tests'],'limitations':[]}


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.top=Path(self.temp.name);self.remote=self.top/'remote';self.remote.mkdir()
        self.real_git=runtime.git
        self.g(['init','-b','main'],self.remote)
        (self.remote/'automation').mkdir()
        (self.remote/'automation/a.py').write_text('original\n')
        (self.remote/'automation/obsolete.txt').write_text('remove in rework\n')
        self.commit(self.remote,'baseline')
        self.branch='agent/R-1-S-1';self.g(['checkout','-b',self.branch],self.remote)
        (self.remote/'automation/a.py').write_text('first submission\n');self.commit(self.remote,'first candidate')
        self.base=self.g(['rev-parse','HEAD'],self.remote)
        self.g(['checkout','main'],self.remote)
        (self.remote/'controller.txt').write_text('trusted main only\n');self.commit(self.remote,'newer trusted main')
        self.root=self.top/'controller'
        self.g(['clone','--depth','1','--branch','main',self.remote.as_uri(),str(self.root)],self.top)
        self.assertEqual(self.g(['rev-parse','--verify',self.base+'^{commit}'],self.root,check=False),'')
        self.home=self.root/'.sdlc/workspaces/worker';self.home.parent.mkdir(parents=True)
        self.g(['clone',self.remote.as_uri(),str(self.home)],self.top);self.g(['checkout','--detach',self.base],self.home)
        self.before=runtime.scan_files(self.home)
        (self.home/'automation/a.py').write_text('corrected second submission\n')
        (self.home/'automation/obsolete.txt').unlink()
        (self.home/'automation/new.py').write_text('new fixture\n')
        self.after=runtime.scan_files(self.home);self.changed=runtime.changes(self.before,self.after)
        self.allowed=['automation/']
        self.bundle=runtime.source_bundle(self.home,self.before,self.after,self.changed,self.allowed,source={})
        self.now=1000.;self.control=Control(self.root/'.sdlc/state.db',{'founder'},clock=lambda:self.now)
        self.control.create_release('R-1','Fixture','lead');self.control.upsert_story('R-1','S','Rework',
            {'allowed_paths':self.allowed,'acceptance':['Correct rework'],'role':'devops','kind':'infrastructure'},[],'lead')
        self.control.submit_plan('R-1',PLAN,'lead');self.control.approve_plan('R-1',PLAN,'founder')
        first=self.control.claim('R-1','S','first',lease_seconds=60)
        self.pr_url='https://github.com/test/repo/pull/68'
        self.control.associate_pr('R-1','S',self.base,self.pr_url,'first','controller',lease_id=first['lease_id'])
        self.control.record_review('R-1','S',self.base,'independent','REQUEST_CHANGES',{'actual':'code issue'},'independent')
        self.lease=self.control.claim('R-1','S','second',lease_seconds=60)
        self.result={'role':'devops','reference':'R-1:story:S','kind':'story','revision':self.base,
            'worker_id':'second','lease_id':self.lease['lease_id'],'plan_hash':PLAN,'workspace':str(self.home),
            'baseline':self.before,'after':self.after,'changed_paths':self.changed,'source_bundle':self.bundle,'report':REPORT}
        self.out=self.root/'.sdlc/output';self.out.mkdir();(self.out/'worker-result.json').write_text(json.dumps(self.result))
        self.client=MagicMock();self.client.root='/repos/test/repo';self.client.repository='test/repo';self.client.token='fixture-controller-token'
        self.client.pr.side_effect=lambda number:self.pr()
        self.client.pages.side_effect=lambda path:self.files()
        self.client.request.side_effect=AssertionError('Existing-task rework must not create a PR or mutate another endpoint.')
        self.p=copy.deepcopy(cli.policy());self.p['repository']['full_name']='test/repo';self.p['repository']['default_branch']='main'
        self.values={};self.git_calls=[];self.fetch_fails=False

    def g(self,args,cwd,**kwargs):return self.real_git(args,cwd,**kwargs)

    def commit(self,path,message):
        self.g(['add','.'],path)
        self.g(['-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-m',message],path)

    def pr(self):
        return {'number':68,'html_url':self.pr_url,'state':'open','user':{'login':'github-actions[bot]'},
                'head':{'sha':self.g(['rev-parse','refs/heads/'+self.branch],self.remote),'ref':self.branch,'repo':{'full_name':'test/repo'}},
                'base':{'ref':'main','repo':{'full_name':'test/repo'}},'changed_files':len(self.files())}

    def files(self):
        names=self.g(['diff','--name-only','main...'+self.branch],self.remote).splitlines()
        return [{'filename':name,'status':'modified','patch':'fixture changed bytes'} for name in names]

    def git_boundary(self,args,cwd,**kwargs):
        self.git_calls.append(list(args))
        if args[0] in {'fetch','push'} and args[1]=='https://github.com/test/repo.git':
            if args[0]=='fetch' and self.fetch_fails:raise RuntimeError('Fixture base object is unavailable')
            args=[args[0],self.remote.as_uri(),*args[2:]]
            kwargs.pop('token',None)
        return self.real_git(args,cwd,**kwargs)

    def publish(self):
        def kv(key,value=None,write=False):
            if write:self.values[key]=value
            return self.values.get(key)
        with patch.object(cli,'ROOT',self.root),patch.object(cli,'OUT',self.out),\
             patch.object(cli,'git',side_effect=self.git_boundary),patch.object(runtime,'git',side_effect=self.git_boundary),\
             patch.object(cli,'kv',side_effect=kv):
            return cli.publish_result(self.p,self.client,self.control)

    def test_shallow_main_fetches_exact_missing_rework_base_and_fastforwards_same_pr(self):
        old_reviews=self.control.events();self.publish();item=self.control.snapshot('R-1')['items'][0]
        self.assertEqual(item['status'],'SUBMITTED');self.assertEqual(item['pr_url'],self.pr_url)
        self.assertEqual(item['attempts'],2);self.assertNotEqual(item['head_sha'],self.base)
        self.assertEqual(self.g(['rev-parse',self.branch+'^'],self.remote),self.base)
        self.assertEqual(self.g(['show',self.branch+':automation/a.py'],self.remote),'corrected second submission')
        self.assertEqual(self.g(['show',self.branch+':automation/new.py'],self.remote),'new fixture')
        self.assertEqual(self.g(['ls-tree','--name-only',self.branch,'automation/obsolete.txt'],self.remote),'')
        self.assertTrue(any(call[:2]==['fetch','https://github.com/test/repo.git'] and call[2]==self.base for call in self.git_calls))
        pushes=[call for call in self.git_calls if call[0]=='push']
        self.assertEqual(pushes,[['push','https://github.com/test/repo.git','HEAD:refs/heads/'+self.branch]])
        self.client.request.assert_not_called();self.assertEqual(self.control.events()[:len(old_reviews)],old_reviews)
        with self.control._tx(False) as db:
            with self.assertRaises(ValueError):self.control._pr_ready(db,item)

    def test_missing_fetch_fails_before_push_and_retained_bytes_survive(self):
        self.fetch_fails=True;before=self.control.snapshot()
        with self.assertRaises(RuntimeError):self.publish()
        self.assertEqual(self.control.snapshot(),before)
        self.assertFalse(any(call[0]=='push' for call in self.git_calls))
        retained=json.loads((self.out/'worker-result.json').read_text())
        self.assertEqual(base64.b64decode(retained['source_bundle']['files']['automation/a.py']),(self.home/'automation/a.py').read_bytes())

    def test_head_race_closed_and_fork_pr_never_associate_or_create_new_pr(self):
        for mode in ('race','closed','fork'):
            with self.subTest(mode=mode):
                calls=[0];original=self.pr
                def pr(number):
                    calls[0]+=1;value=original()
                    if mode=='closed':value['state']='closed'
                    if mode=='fork':value['head']['repo']['full_name']='attacker/fork'
                    if mode=='race' and calls[0]>1:value['head']['sha']='f'*40
                    return value
                self.client.pr.side_effect=pr;before=self.control.snapshot();self.git_calls=[]
                with self.assertRaises(ValueError):self.publish()
                self.assertEqual(self.control.snapshot(),before)
                self.assertFalse(any(call[0]=='push' for call in self.git_calls));self.client.request.assert_not_called()

    def test_retained_bundle_publishes_without_worker_git_or_workspace(self):
        # The publisher consumes validated retained bytes, never model Git config.
        result=copy.deepcopy(self.result);result['workspace']=str(self.top/'missing-original-worker')
        (self.out/'worker-result.json').write_text(json.dumps(result))
        self.publish();self.assertEqual(self.control.snapshot('R-1')['items'][0]['status'],'SUBMITTED')

    def test_hash_only_historical_result_without_workspace_is_not_invented(self):
        result=copy.deepcopy(self.result);result.pop('source_bundle');result['workspace']=str(self.root/'.sdlc/workspaces/lost')
        (self.out/'worker-result.json').write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'No retained source bytes'):self.publish()
        self.assertFalse(any(call[0]=='push' for call in self.git_calls))

    def test_publisher_checks_its_credential_even_if_it_was_absent_from_worker_environment(self):
        (self.home/'automation/a.py').write_bytes(self.client.token.encode())
        result=copy.deepcopy(self.result);result['after']=runtime.scan_files(self.home)
        result['source_bundle']=runtime.source_bundle(self.home,result['baseline'],result['after'],self.changed,self.allowed,source={})
        (self.out/'worker-result.json').write_text(json.dumps(result))
        before=self.control.snapshot()
        with self.assertRaises(ValueError) as caught:self.publish()
        self.assertNotIn(self.client.token,str(caught.exception))
        self.assertEqual(self.control.snapshot(),before)
        self.assertFalse(any(call[0]=='push' for call in self.git_calls))

    def test_worker_persists_verified_bytes_before_a_later_publisher_fetch_failure(self):
        c=Control(self.root/'.sdlc/worker-test.db',{'founder'},clock=lambda:self.now)
        c.create_release('R-2','Worker fixture','lead');c.upsert_story('R-2','G','Write fixture',
            {'allowed_paths':['automation/'],'acceptance':['Write source'],'role':'devops','kind':'infrastructure'},[],'lead')
        c.submit_plan('R-2',PLAN,'lead');c.approve_plan('R-2',PLAN,'founder')
        roles=self.root/'agents/roles';roles.mkdir(parents=True);(roles/'devops.md').write_text('Trusted fixture role')
        self.values['queue:devops:R-2:story:G']={'revision':self.base}
        def kv(key,value=None,write=False):
            if write:self.values[key]=value
            return self.values.get(key)
        def agent(workspace,*args,**kwargs):
            (workspace/'automation/a.py').write_bytes(b'retained before publication\n')
            (workspace/'.git/config').write_text('invalid model-mutated Git metadata must never be executed')
            return REPORT
        with patch.object(cli,'ROOT',self.root),patch.object(cli,'OUT',self.out),patch.object(cli,'ledger',return_value=c),\
             patch.object(cli,'current_plan',return_value=({'document':{}},PLAN)),patch.object(cli,'kv',side_effect=kv),\
             patch.object(cli,'git',side_effect=self.git_boundary),patch.object(runtime,'git',side_effect=self.git_boundary),\
             patch.object(cli.DockerAgent,'run',side_effect=agent):
            result=cli.worker(self.p,Namespace(role='devops',task_id='R-2:story:G',revision=self.base,event_path=None))
            self.assertEqual(base64.b64decode(result['source_bundle']['files']['automation/a.py']),b'retained before publication\n')
            self.fetch_fails=True
            with self.assertRaises(RuntimeError):cli.publish_result(self.p,self.client,c)
        retained=json.loads((self.out/'worker-result.json').read_text())
        self.assertEqual(retained['source_bundle'],result['source_bundle'])
        self.assertFalse(any(call[0]=='push' for call in self.git_calls))


class SourceBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.work=self.root/'worker';self.work.mkdir()
        (self.work/'a.txt').write_bytes(b'old');(self.work/'delete.txt').write_bytes(b'old')
        self.before=runtime.scan_files(self.work)
        (self.work/'a.txt').write_bytes(b'new');(self.work/'delete.txt').unlink()
        self.after=runtime.scan_files(self.work);self.changed=runtime.changes(self.before,self.after)

    def bundle(self,source=None):return runtime.source_bundle(self.work,self.before,self.after,self.changed,['a.txt','delete.txt'],source=source or {})

    def test_source_bundle_binds_hashes_deletions_allowlist_and_caps(self):
        bundle=self.bundle();self.assertIsNone(bundle['files']['delete.txt'])
        self.assertEqual(runtime.validate_source_bundle(bundle,self.before,self.after,self.changed,['a.txt','delete.txt'],source={})['a.txt'],b'new')
        broken=copy.deepcopy(bundle);broken['files']['a.txt']=base64.b64encode(b'tampered').decode()
        with self.assertRaises(ValueError):runtime.validate_source_bundle(broken,self.before,self.after,self.changed,['a.txt','delete.txt'])
        with self.assertRaises(ValueError):runtime.validate_source_bundle(bundle,self.before,self.after,self.changed,['a.txt'])
        with patch.object(runtime,'MAX_SOURCE_BYTES',2):
            with self.assertRaises(ValueError):self.bundle()
        with patch.object(runtime,'MAX_SOURCE_FILES',1):
            with self.assertRaises(ValueError):self.bundle()
        broken=copy.deepcopy(bundle);broken['files']['delete.txt']=base64.b64encode(b'not deleted').decode()
        with self.assertRaises(ValueError):runtime.validate_source_bundle(broken,self.before,self.after,self.changed,['a.txt','delete.txt'])

    def test_credentials_are_rejected_without_retaining_raw_values(self):
        for value,source in [(b'fixture-private-token',{'GH_TOKEN':'fixture-private-token'}),(b'ghp_'+b'fixtureSecret123456789',{})]:
            with self.subTest(source=bool(source)):
                (self.work/'a.txt').write_bytes(value);self.after=runtime.scan_files(self.work)
                with self.assertRaises(ValueError) as caught:self.bundle(source)
                self.assertNotIn(value.decode(),str(caught.exception))


if __name__=='__main__':unittest.main()
