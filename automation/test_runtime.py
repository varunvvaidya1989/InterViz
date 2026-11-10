import argparse
import base64
import copy
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.control import Control
from automation.github import GitHubError,SnapshotStore,sign_snapshot,verify_snapshot,repository_name
from automation.providers import DockerAgent,check_changed_paths,sanitized_environment,validate_report
from automation.runtime import digest,plan_document,scan_files,publish_copy
from automation import cli


class RuntimeTests(unittest.TestCase):
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
