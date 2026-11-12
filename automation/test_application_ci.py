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
                     'base': {'repo': {'full_name': self.repository}}, 'user': {'login': 'coder'}}
        self.runs = {}
        self.jobs = {}
        self.blobs = {}
        for number, filename, names in [(1, 'infrastructure-ci.yml', ['sdlc-infrastructure-ci']),
                                         (2, 'application-ci.yml', ['application-unit-integration', 'application-e2e'])]:
            path = '.github/workflows/' + filename
            run = dict(id=number, run_number=number, run_attempt=1, workflow_id=number, path=path,
                       repository={'full_name': self.repository}, head_repository={'full_name': self.repository},
                       head_sha=H, event='pull_request', pull_requests=[{'number': 1}],
                       status='completed', conclusion='success')
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
        with patch.object(cli, 'pr_files', return_value=([], [])), patch.object(cli, 'kv', return_value=None):
            cli.record_ci_run(self.p, self.api, self.control, {'conclusion': 'success'})

    def ready(self):
        with sqlite3.connect(self.control.path) as db:
            db.row_factory = sqlite3.Row
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
        run.update(id=3, run_number=3, conclusion='cancelled')
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
        with patch.object(cli, 'pr_files', return_value=([], [])), patch.object(cli, 'kv', return_value={'pr': 1}):
            cli.record_ci_run(self.p, self.api, self.control, {})
        self.ready()
