import argparse
import base64
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from automation.control import Control
from automation.github import GitHubError,SnapshotStore,sign_snapshot,verify_snapshot,repository_name
from automation.providers import DockerAgent,check_changed_paths,sanitized_environment,validate_report
from automation.runtime import digest,plan_document,scan_files,publish_copy
from automation import cli


class RuntimeTests(unittest.TestCase):
    def test_ci_waits_for_approval_and_preserves_existing_receipts(self):
        p=cli.policy();target='a'*40;values={}
        client=MagicMock();client.root='/repos/test/repo';client.repository='test/repo'
        client.request.return_value={'id':7}
        client.pr.return_value={'number':51,'head':{'sha':target,'repo':{'full_name':client.repository}},'html_url':'fixture://pr/51'}
        client.info.return_value={'default_branch':'main'}
        client.file.return_value={'sha':'unchanged-workflow'}
        control=MagicMock()
        control.snapshot.return_value={'items':[{'release_id':'R','id':'S','kind':'story','pr_url':'fixture://pr/51','head_sha':target}]}
        def kv(key,value=None,write=False):
            if write:values[key]=value
            return values.get(key)
        run={'id':123,'workflow_id':7,'status':'completed','event':'pull_request','pull_requests':[{'number':51}],'head_sha':target,'html_url':'fixture://run/123','run_attempt':1,'conclusion':'action_required'}
        with patch.object(cli,'kv',side_effect=kv), patch.object(cli,'pr_files',return_value=([],[])):
            cli.record_ci_run(p,client,control,run)
            control.record_ci.assert_not_called();self.assertEqual(values,{})
            run['conclusion']='success'
            cli.record_ci_run(p,client,control,run)
            self.assertTrue(control.record_ci.call_args.args[3])
            cli.record_ci_run(p,client,control,run)
            self.assertEqual(control.record_ci.call_count,1)
            self.assertEqual(set(values),{'ci-run:123'})
            # Existing receipts are authoritative; a controller upgrade must not
            # replay historical runs in reverse order over current evidence.
            values.update({'ci-run:200':{'processed':True},'ci-run:100':{'processed':True}})
            for run_id,conclusion in [(200,'failure'),(100,'success')]:
                run.update(id=run_id,conclusion=conclusion)
                cli.record_ci_run(p,client,control,run)
            self.assertEqual(control.record_ci.call_count,1)

    def test_review_checks_exact_candidate_with_trusted_instructions_and_fails_closed(self):
        p=cli.policy()
        # A real repository/clone catches the original bug: the reviewer saw the
        # controller HEAD and could not see files introduced by the candidate.
        for mode in ('local', 'fetch', 'missing', 'mismatch'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                remote=Path(directory)/'remote';remote.mkdir()
                def git(args, cwd):
                    return cli.git(args,cwd)
                git(['init'],remote)
                git(['config','user.name','Fixture'],remote)
                git(['config','user.email','fixture@example.test'],remote)
                (remote/'agents/roles').mkdir(parents=True)
                (remote/'agents/roles/qa.md').write_text('TRUSTED_REVIEW_ROLE')
                git(['add','.'],remote);git(['commit','-m','trusted baseline'],remote)
                root=Path(directory)/'controller'
                git(['clone','--no-hardlinks',str(remote),str(root)],Path(directory))
                baseline=git(['rev-parse','HEAD'],root)
                (remote/'candidate.txt').write_text('candidate evidence')
                (remote/'agents/roles/qa.md').write_text('UNTRUSTED_CANDIDATE_ROLE')
                git(['add','.'],remote);git(['commit','-m','candidate'],remote)
                target=git(['rev-parse','HEAD'],remote)
                if mode=='local':git(['fetch',str(remote),target],root)
                control=MagicMock()
                control.snapshot.return_value={'releases':[{'plan_approved_hash':'approved'}]}
                item={'status':'SUBMITTED','head_sha':target,'scope':{'allowed_paths':['candidate.txt']}}
                args=argparse.Namespace(role='review',task_id='R:story:S',revision=target)
                values={'queue:review:R:story:S':{'revision':target,'diff':'authenticated candidate diff'}}
                def kv(key,value=None,write=False):
                    if write:values[key]=value
                    return values.get(key)
                real_git=cli.git
                def controller_git(arguments,cwd,**kwargs):
                    if arguments[0]=='fetch' and arguments[1].startswith('https://'):
                        if mode=='missing':raise RuntimeError('Candidate unavailable')
                        arguments=['fetch',str(remote),arguments[2]]
                    if mode=='mismatch' and arguments==['rev-parse','HEAD'] and Path(cwd)!=root:
                        return baseline
                    return real_git(arguments,cwd,**kwargs)
                report={'summary':'Fixture review','verdict':'APPROVE','findings':[],'evidence':[],'limitations':[]}
                def review(home,role,provider,prompt,**kwargs):
                    self.assertEqual(real_git(['rev-parse','HEAD'],home),target)
                    self.assertEqual((home/'candidate.txt').read_text(),'candidate evidence')
                    self.assertIn('TRUSTED_REVIEW_ROLE',prompt)
                    self.assertNotIn('UNTRUSTED_CANDIDATE_ROLE',prompt)
                    self.assertIn('authenticated candidate diff',prompt)
                    self.assertIn(target,prompt)
                    self.assertEqual(role,'review')
                    return report
                with patch.object(cli,'ROOT',root), patch.object(cli,'ledger',return_value=control), \
                     patch.object(cli,'find_item',return_value=('R','story','S',item)), \
                     patch.object(cli,'current_plan',return_value=({'document':{}},'approved')), \
                     patch.object(cli,'kv',side_effect=kv), patch.object(cli,'git',side_effect=controller_git), \
                     patch.object(cli,'output',side_effect=lambda name,value:value), \
                     patch.object(DockerAgent,'run',side_effect=review) as agent:
                    if mode in {'missing','mismatch'}:
                        with self.assertRaisesRegex((RuntimeError,ValueError),'Candidate unavailable|exact target revision'):
                            cli.worker(p,args)
                        agent.assert_not_called()
                    else:
                        result=cli.worker(p,args)
                        self.assertEqual(result['revision'],target)
                        self.assertEqual(result['changed_paths'],[])
                        agent.assert_called_once()
                self.assertEqual(real_git(['rev-parse','HEAD'],root),baseline)

    def test_credentials_never_reach_provider_subprocess(self):
        env=sanitized_environment('codex',{'PATH':'/bin','OPENAI_API_KEY':'test-only','GH_TOKEN':'never-copy','GITHUB_TOKEN':'never-copy','SDLC_STATE_SIGNING_KEY':'never-copy','AWS_SECRET_ACCESS_KEY':'never-copy'})
        self.assertEqual(set(env),{'PATH','OPENAI_API_KEY'})

    def test_provider_command_is_bounded_and_review_is_read_only(self):
        command=DockerAgent().command(Path.cwd(),'review','codex')
        self.assertIn('--cap-drop=ALL',command);self.assertIn('--memory=4g',command)
        self.assertEqual(command[command.index('--sandbox')+1],'read-only')
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',command)
        self.assertNotIn('GH_TOKEN',' '.join(command));self.assertNotIn('docker.sock',' '.join(command))
        self.assertIn('CODEX_API_KEY',command)
        self.assertIn('--interactive',command)

    def test_sandbox_failure_precedes_paid_model_call_and_receives_no_key(self):
        calls=[]
        def runner(command,**kwargs):
            calls.append((command,kwargs))
            return subprocess.CompletedProcess(command,1,'','No permissions to create a new namespace')
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'OPENAI_API_KEY':'fixture-never-real','GH_TOKEN':'fixture-controller-only'}):
            with self.assertRaisesRegex(RuntimeError,'no paid model task'):
                DockerAgent(runner=runner).run(directory,'coding','codex','fixture')
        self.assertEqual(len(calls),1)
        self.assertNotIn('OPENAI_API_KEY',calls[0][1]['env'])
        self.assertNotIn('CODEX_API_KEY',calls[0][1]['env'])
        self.assertNotIn('GH_TOKEN',calls[0][1]['env'])

    def test_path_scope_protected_paths_and_traversal(self):
        check_changed_paths(['apps/web/a.ts'],['apps/web/'])
        for path in ['../outside','C:/secret','/etc/passwd','.git/config','packages/other.ts']:
            with self.subTest(path=path),self.assertRaises(ValueError):check_changed_paths([path],['apps/web/'])
        with self.assertRaises(ValueError):check_changed_paths(['automation/policy.json'],['automation/'],['automation/'])

    def test_report_never_grants_authority(self):
        valid={'summary':'Reviewed','verdict':'APPROVE','findings':[],'evidence':[],'limitations':[]}
        self.assertEqual(validate_report(valid),valid)
        with self.assertRaises(ValueError):validate_report({**valid,'founder_approved':True})
        with self.assertRaises(ValueError):validate_report({**valid,'verdict':'MERGE_NOW'})

    def test_signed_snapshot_tamper_is_rejected(self):
        key='test-only-signing-key-'*3
        envelope=sign_snapshot(b'SQLite format 3\x00test',key)
        self.assertEqual(verify_snapshot(envelope,key),b'SQLite format 3\x00test')
        envelope['database']=base64.b64encode(b'SQLite format 3\x00changed').decode()
        with self.assertRaises(ValueError):verify_snapshot(envelope,key)
        with self.assertRaises(ValueError):sign_snapshot(b'data','short')

    def test_snapshot_restore_and_stale_compare_and_swap(self):
        class Fake:
            root='/repos/test/repo'
            item=None
            def file(self,*args):
                if self.item is None:raise GitHubError('absent',404)
                return copy.deepcopy(self.item)
            def ensure_branch(self,*args):return {}
            def request(self,method,path,body):
                prior=self.item['sha'] if self.item else None
                if body.get('sha')!=prior:raise GitHubError('stale',409)
                sha=digest(body['content'].encode());self.item={'sha':sha,'content':body['content']};return {'content':{'sha':sha}}
        with tempfile.TemporaryDirectory() as directory:
            fake=Fake();key='fixture-signing-key-'*3
            first=SnapshotStore(fake,Path(directory)/'one.db',key)
            self.assertTrue(first.restore()['initial']);Control(first.db,founder_ids=['founder']).create_release('R','Release','founder');first.save()
            second=SnapshotStore(fake,Path(directory)/'two.db',key);self.assertTrue(second.restore()['restored'])
            self.assertEqual(Control(second.db).snapshot()['releases'][0]['id'],'R')
            Control(second.db).create_release('R2','Second','worker');second.save()
            with self.assertRaises(GitHubError):first.save()

    def test_plan_hash_binds_scope_and_policy(self):
        p=cli.policy()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'planning').mkdir();(root/'planning/Systems Labs Product Specification.md').write_text('fixture')
            plan={'release_id':'R','user_stories':[{'id':'S','title':'Feature','allowed_paths':['apps/web/'],'acceptance':['works'],'depends_on':[]}],**{k:'draft section' for k in p['gates']['plan_approval']['required_sections'] if k!='user_stories'}}
            path=root/'plan.json';path.write_text(json.dumps(plan));_,one=plan_document(path,p,root)
            plan['user_stories'][0]['acceptance']=['changed'];path.write_text(json.dumps(plan));_,two=plan_document(path,p,root);self.assertNotEqual(one,two)
            changed=copy.deepcopy(p);changed['limits']['max_attempts']=1;_,three=plan_document(path,changed,root);self.assertNotEqual(two,three)

    def test_plan_rejects_cycles(self):
        p=cli.policy()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'planning').mkdir();(root/'planning/Systems Labs Product Specification.md').write_text('fixture')
            plan={'release_id':'R','user_stories':[{'id':'S','title':'Feature','allowed_paths':['apps/web/'],'acceptance':['works'],'depends_on':['S']}],**{k:'draft' for k in p['gates']['plan_approval']['required_sections'] if k!='user_stories'}}
            path=root/'plan.json';path.write_text(json.dumps(plan))
            with self.assertRaises(ValueError):plan_document(path,p,root)

    def test_publisher_copies_bytes_not_git_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'worker';clean=Path(directory)/'clean';source.mkdir();clean.mkdir()
            (source/'.git').mkdir();(source/'.git/config').write_text('malicious metadata')
            (source/'feature.txt').write_text('reviewed bytes')
            publish_copy(source,clean,['feature.txt'])
            self.assertEqual((clean/'feature.txt').read_text(),'reviewed bytes');self.assertFalse((clean/'.git').exists())
            self.assertNotIn('.git/config',scan_files(source))

    def test_github_actor_cannot_be_claimed_by_payload(self):
        class Fake:
            root='/repos/test/repo';repository='test/repo'
            def request(self,*args):return {'actor':{'login':'actual'},'repository':{'full_name':'test/repo'}}
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_RUN_ID':'123','GITHUB_ACTOR':'forged'}):
            with self.assertRaises(ValueError):cli.principal({},Fake())

    def test_unconfigured_app_or_staging_never_passes(self):
        p=cli.policy()
        with self.assertRaises(ValueError):cli.validate(p,'application')
        with self.assertRaises(ValueError):cli.validate(p,'staging')
        inactive=copy.deepcopy(p);inactive['execution_mode']='dry-run'
        with self.assertRaises(ValueError):cli.require_live(inactive)

    def test_repository_names_are_not_arbitrary_urls(self):
        self.assertEqual(repository_name('owner/repo'),'owner/repo')
        for name in ['https://evil.example/repo','owner/repo/../../x','owner;echo/x']:
            with self.assertRaises(ValueError):repository_name(name)

    def test_every_pr_head_revalidates_complete_scope(self):
        class Fake:
            root='/repos/test/repo'
            def pages(self,*args):return [{'filename':'automation/policy.json','patch':'changed'}]
        with self.assertRaises(ValueError):cli.pr_files(Fake(),{'number':1,'changed_files':1},{'scope':{'allowed_paths':['apps/web/']}},cli.policy())

    def test_missing_file_pagination_never_passes_review(self):
        class Fake:
            root='/repos/test/repo'
            def pages(self,*args):return [{'filename':'apps/web/a.ts','patch':'changed'}]
        with self.assertRaises(ValueError):cli.pr_files(Fake(),{'number':1,'changed_files':2},{'scope':{'allowed_paths':['apps/web/']}},cli.policy())

    def test_controller_state_requires_key_before_mutations(self):
        with self.assertRaises(ValueError):SnapshotStore(object(),'fixture.db',None)


if __name__=='__main__':unittest.main()
