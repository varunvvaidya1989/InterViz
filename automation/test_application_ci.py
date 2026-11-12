"""Fake authenticated GitHub transport against a real isolated controller ledger."""
import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import cli
from automation.control import Control, ControlError

H = 'b' * 40


class API:
    repository = 'fixture/repo'
    root = '/repos/fixture/repo'

    def __init__(self):
        self.pull = {'number': 1, 'html_url': 'https://fixture/pull/1',
                     'head': {'sha': H, 'repo': {'full_name': self.repository}},
                     'base': {'ref': 'main', 'repo': {'full_name': self.repository}}, 'user': {'login': 'coder'}}
        self.runs = {}
        self.jobs = {}
        self.blobs = {}
        for number, filename, names in [(1, 'infrastructure-ci.yml', ['sdlc-infrastructure-ci']),
                                         (2, 'application-ci.yml', ['application-unit-integration', 'application-e2e'])]:
            path = '.github/workflows/' + filename
            run = dict(id=number, run_number=number, run_attempt=1, workflow_id=number, path=path,
                       repository={'full_name': self.repository}, head_repository={'full_name': self.repository},
                       head_sha=H, event='pull_request', pull_requests=[{'number': 1}],
                       status='completed', conclusion='success', updated_at=f'2026-11-12T10:00:0{number}Z')
            self.runs[filename] = [run]
            self.jobs[number] = [dict(id=10+i, name=name, run_id=number, run_attempt=1,
                                     status='completed', conclusion='success') for i, name in enumerate(names)]

    def info(self): return {'default_branch': 'main'}
    def pr(self, number): return copy.deepcopy(self.pull)
    def file(self, path, ref): return {'sha': self.blobs.get((path, ref), 'trusted-blob')}
    def request(self, method, path):
        assert method == 'GET'
        if '/actions/workflows/' in path:
            filename = path.rsplit('/', 1)[1]
            return {'id': 1 if filename == 'infrastructure-ci.yml' else 2,
                    'path': '.github/workflows/' + filename}
        number = int(path.rsplit('/', 1)[1])
        return copy.deepcopy(next(r for runs in self.runs.values() for r in runs if r['id'] == number))
    def pages(self, path, key=None):
        if path.endswith('/runs'):
            return copy.deepcopy(self.runs[path.split('/')[-2]])
        return copy.deepcopy(self.jobs[int(path.split('/actions/runs/')[1].split('/')[0])])


class ApplicationCI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.control = Control(Path(self.temp.name)/'ledger.sqlite3', {'founder'})
        self.control.create_release('R', 'fixture', 'lead')
        self.control.upsert_story('R', 'S', 'app', {'kind': 'application', 'allowed_paths': ['apps/'], 'acceptance': ['works']}, [], 'lead')
        self.control.submit_plan('R', 'a'*64, 'lead'); self.control.approve_plan('R', 'a'*64, 'founder')
        lease = self.control.claim('R', 'S', 'coder')
        self.control.associate_pr('R', 'S', H, 'https://fixture/pull/1', 'coder', 'github', lease_id=lease['lease_id'])
        self.control.record_review('R', 'S', H, 'reviewer', 'APPROVE', {'fixture': True}, 'reviewer')
        self.p = cli.policy()
        self.p['repository']['full_name'] = 'fixture/repo'
        self.p['checks']['application_configured'] = True
        self.p['gates']['required_application_status_checks'] = ['application-unit-integration', 'application-e2e']
        self.api = API()

    def record(self):
        with patch.object(cli, 'pr_files', return_value=([], [])), patch.object(cli, 'kv', return_value=None), \
             patch.object(cli,'require_current_plan',return_value=({},'a'*64)):
            cli.record_ci_run(self.p, self.api, self.control, {'conclusion': 'success'})

    def ready(self):
        with self.control._tx(False) as db:
            self.control._pr_ready(db, self.control.snapshot()['items'][0])

    def blocked(self):
        with self.assertRaises(ControlError): self.ready()

    def test_complete_trusted_checks_permit_gate_then_failed_rerun_revokes(self):
        self.record(); self.ready()
        run = self.api.runs['application-ci.yml'][0]
        run.update(run_attempt=2, conclusion='failure')
        self.record(); self.blocked()

    def test_missing_pending_failed_skipped_cancelled_stale_forged_and_changed_workflow(self):
        original = copy.deepcopy(self.api)
        mutations = [lambda a: a.jobs[2].pop(),
                     lambda a: a.runs['application-ci.yml'].clear(),
                     lambda a: a.runs['application-ci.yml'][0].update(head_sha='d'*40),
                     lambda a: a.runs['application-ci.yml'][0].update(workflow_id=999),
                     lambda a: a.runs['application-ci.yml'][0].update(repository={'full_name': 'evil/repo'}),
                     lambda a: a.jobs[2][0].update(run_attempt=2),
                     lambda a: a.blobs.update({('.github/workflows/application-ci.yml', H): 'changed'})]
        mutations += [lambda a, status=s: a.jobs[2][0].update(conclusion=status)
                      for s in ['failure', 'skipped', 'cancelled', None]]
        mutations += [lambda a: a.runs['application-ci.yml'][0].update(status='in_progress')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.api = copy.deepcopy(original)
                self.record(); self.ready()
                mutate(self.api); self.record(); self.blocked()

    def test_newer_run_supersedes_success_independent_of_list_order(self):
        run = copy.deepcopy(self.api.runs['application-ci.yml'][0])
        run.update(id=3, run_number=3, conclusion='cancelled', updated_at='2026-11-12T10:00:03Z')
        self.api.runs['application-ci.yml'].insert(0, run)
        self.api.jobs[3] = []
        self.record(); self.blocked()

    def test_new_head_invalidates_review_and_ci(self):
        self.record(); self.ready()
        self.api.pull['head']['sha'] = 'd'*40
        self.record(); self.blocked()
        self.assertEqual('d'*40, self.control.snapshot()['items'][0]['head_sha'])

    def test_unavailable_api_revokes_prior_green(self):
        self.record(); self.ready()
        from automation.github import GitHubError
        with patch.object(self.api, 'pages', side_effect=GitHubError('fixture unavailable')):
            self.record()
        self.blocked()

    def test_dispatch_requires_matching_queue_receipt(self):
        run = self.api.runs['application-ci.yml'][0]
        run.update(event='workflow_dispatch', head_branch='main', display_title='SDLC CI workflow_dispatch pr=1 sha='+H)
        self.record(); self.blocked()
        with patch.object(cli, 'pr_files', return_value=([], [])), patch.object(cli, 'kv', return_value={'pr': 1}), \
             patch.object(cli,'require_current_plan',return_value=({},'a'*64)):
            cli.record_ci_run(self.p, self.api, self.control, {})
        self.ready()

    def add_newer_success(self, stamp='2026-11-12T10:00:03Z'):
        run=copy.deepcopy(self.api.runs['application-ci.yml'][0])
        run.update(id=3,run_number=3,updated_at=stamp)
        self.api.runs['application-ci.yml'].append(run)
        self.api.jobs[3]=[{**job,'id':job['id']+20,'run_id':3} for job in self.api.jobs[2]]
        return run

    def test_integrated_item_failed_rerun_revokes_downstream_eligibility(self):
        self.record();self.control.integrate('R','S',H,'c'*40,'controller')
        self.api.runs['application-ci.yml'][0].update(run_attempt=2,conclusion='failure',updated_at='2026-11-12T10:00:04Z')
        self.record();self.blocked()
        self.assertEqual(self.control.snapshot()['items'][0]['status'],'INTEGRATED')
        with self.assertRaises(ControlError):self.control.start_qa('R','c'*40,'qa')

    def test_done_item_failed_rerun_invalidates_qa_and_candidate(self):
        self.record();self.control.integrate('R','S',H,'c'*40,'controller')
        self.control.start_qa('R','c'*40,'qa');self.control.complete_qa('R','c'*40,{'fixture':'QA'},'qa')
        self.api.runs['application-ci.yml'][0].update(run_attempt=2,conclusion='failure',updated_at='2026-11-12T10:00:04Z')
        self.record();self.blocked()
        self.assertFalse(self.control.snapshot()['releases'][0]['qa_passed'])
        with self.assertRaises(ControlError):self.control.freeze_candidate('R','c'*40,'founder')

    def test_later_failed_rerun_of_older_run_supersedes_newer_run_number(self):
        self.add_newer_success();self.record();self.ready()
        self.api.runs['application-ci.yml'][0].update(run_attempt=2,conclusion='failure',updated_at='2026-11-12T10:00:04Z')
        for reverse in (False,True):
            if reverse:self.api.runs['application-ci.yml'].reverse()
            self.record();self.blocked()

    def test_stale_list_summary_cannot_hide_a_current_failed_rerun(self):
        self.add_newer_success();summaries=copy.deepcopy(self.api.runs['application-ci.yml'])
        self.api.runs['application-ci.yml'][0].update(run_attempt=2,conclusion='failure',updated_at='2026-11-12T10:00:04Z')
        original=self.api.pages
        def pages(path,key=None):
            if path.endswith('/application-ci.yml/runs'):return copy.deepcopy(summaries)
            return original(path,key)
        with patch.object(self.api,'pages',side_effect=pages):self.record()
        self.blocked()

    def test_timestamp_ties_require_every_latest_execution_to_pass(self):
        self.add_newer_success('2026-11-12T10:00:02Z');self.record();self.ready()
        self.api.runs['application-ci.yml'][0].update(conclusion='failure')
        self.record();self.blocked()

    def test_missing_invalid_or_timezone_free_execution_recency_revokes_green(self):
        for stamp in (None,'invalid','2026-11-12T10:00:02'):
            with self.subTest(stamp=stamp):
                self.api.runs['application-ci.yml'][0]['updated_at']='2026-11-12T10:00:02Z'
                self.record();self.ready()
                self.api.runs['application-ci.yml'][0]['updated_at']=stamp
                self.record();self.blocked()

    def test_execution_started_while_fetching_jobs_revokes_prior_success(self):
        original=self.api.pages;started=False
        def pages(path,key=None):
            nonlocal started
            if '/runs/2/attempts/1/jobs' in path and not started:
                started=True;new=self.add_newer_success();new.update(status='queued',conclusion=None)
            return original(path,key)
        with patch.object(self.api,'pages',side_effect=pages):self.record()
        self.assertTrue(started);self.blocked()

    def test_integrated_head_change_revokes_ci_without_rewriting_accepted_source(self):
        self.record();self.control.integrate('R','S',H,'c'*40,'controller')
        before=self.control.snapshot()['items'][0]
        self.api.pull['head']['sha']='d'*40;self.record();self.blocked()
        item=self.control.snapshot()['items'][0]
        self.assertEqual((item['head_sha'],item['integration_sha'],item['epoch']),
                         (before['head_sha'],before['integration_sha'],before['epoch']))

    def test_infrastructure_checks_stay_distinct_from_application_checks(self):
        c=Control(Path(self.temp.name)/'infra.sqlite3',{'founder'})
        c.create_release('I','infra','lead')
        c.upsert_story('I','IS','infra',{'kind':'infrastructure','allowed_paths':['automation/'],'acceptance':['works']},[],'lead')
        c.submit_plan('I','a'*64,'lead');c.approve_plan('I','a'*64,'founder')
        claim=c.claim('I','IS','coder');c.associate_pr('I','IS',H,'https://fixture/pull/1','coder','github',lease_id=claim['lease_id'])
        c.record_review('I','IS',H,'reviewer','APPROVE',{'fixture':True},'reviewer')
        self.control=c
        self.api.runs['application-ci.yml'][0]['conclusion']='failure'
        self.record();self.ready()
        self.api.runs['infrastructure-ci.yml'][0]['conclusion']='failure'
        self.record();self.blocked()

    def test_released_history_is_not_mutated_by_later_notifications(self):
        c=self.control;self.record();c.integrate('R','S',H,'c'*40,'controller')
        c.start_qa('R','c'*40,'qa');c.complete_qa('R','c'*40,{'fixture':True},'qa')
        c.freeze_candidate('R','c'*40,'founder');c.approve_release('R','c'*40,'founder')
        c.record_release('R','c'*40,'fixture-release',{'fixture':True},'founder')
        before=c.snapshot();events=c.events()
        self.api.runs['application-ci.yml'][0]['conclusion']='failure';self.record()
        self.assertEqual(c.snapshot(),before);self.assertEqual(c.events(),events)

    def test_stale_current_plan_blocks_api_queries_and_ci_mutations(self):
        before=self.control.snapshot();events=self.control.events()
        with patch.object(cli,'require_current_plan',side_effect=ValueError('stale approval')), \
             patch.object(self.api,'request',wraps=self.api.request) as request, \
             patch.object(self.api,'pr',wraps=self.api.pr) as pr:
            cli.record_ci_run(self.p,self.api,self.control,{})
        request.assert_not_called();pr.assert_not_called()
        self.assertEqual(self.control.snapshot(),before);self.assertEqual(self.control.events(),events)

    def test_unavailable_pr_or_scope_facts_revoke_prior_green_without_leaking_details(self):
        from automation.github import GitHubError
        for mode in ('pr','scope','invalid-scope','leaf-pr'):
            with self.subTest(mode=mode):
                self.record();self.ready()
                with patch.object(cli,'require_current_plan',return_value=({},'a'*64)), \
                     patch.object(cli,'kv',return_value=None):
                    if mode in ('pr','leaf-pr'):
                        with patch.object(self.api,'pr',side_effect=GitHubError('private fixture detail')):
                            if mode=='leaf-pr':
                                from automation import ci
                                ci.reconcile_item(self.p,self.api,self.control,self.control.snapshot()['items'][0],lambda head:None)
                            else:cli.record_ci_run(self.p,self.api,self.control,{})
                    else:
                        error=GitHubError('private fixture detail') if mode=='scope' else ValueError('private fixture detail')
                        with patch.object(cli,'pr_files',side_effect=error):
                            cli.record_ci_run(self.p,self.api,self.control,{})
                self.blocked()
                with self.control._tx(False) as db:
                    row=db.execute('SELECT evidence FROM ci_runs ORDER BY seq DESC LIMIT 1').fetchone()
                    self.assertNotIn('private fixture detail',row['evidence'])

    def test_earlier_workflow_failed_rerun_during_later_workflow_jobs_revokes_green(self):
        self.record();self.ready();original=self.api.pages;changed=False
        def pages(path,key=None):
            nonlocal changed
            if '/runs/2/attempts/1/jobs' in path and not changed:
                changed=True
                self.api.runs['infrastructure-ci.yml'][0].update(
                    run_attempt=2,conclusion='failure',updated_at='2026-11-12T10:00:05Z')
            return original(path,key)
        with patch.object(self.api,'pages',side_effect=pages):self.record()
        self.assertTrue(changed);self.blocked()
        with self.control._tx(False) as db:
            import json
            evidence=json.loads(db.execute('SELECT evidence FROM ci_runs ORDER BY seq DESC LIMIT 1').fetchone()['evidence'])
        self.assertEqual(evidence['workflows'][0]['result'],'execution_changed_after_collection')
        self.assertEqual(evidence['workflows'][0]['current_executions'][0]['conclusion'],'failure')

    def test_head_race_after_scope_verification_never_associates_unverified_source(self):
        self.record();self.ready();before=self.control.snapshot()['items'][0]
        first=copy.deepcopy(self.api.pull);first['head']['sha']='d'*40
        second=copy.deepcopy(first);second['head']['sha']='e'*40
        with patch.object(self.api,'pr',side_effect=[first,second]):self.record()
        self.blocked();item=self.control.snapshot()['items'][0]
        self.assertEqual((item['head_sha'],item['epoch'],item['author_ids']),
                         (before['head_sha'],before['epoch'],before['author_ids']))
