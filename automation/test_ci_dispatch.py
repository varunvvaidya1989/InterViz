"""Offline dispatch regressions; no hosted Actions or live ledger access."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import cli

HEAD = 'a' * 40


class Client:
    repository = 'owner/repo'
    root = '/repos/owner/repo'

    def __init__(self):
        self.current = {'number': 7, 'html_url': 'https://github.com/owner/repo/pull/7',
                        'head': {'sha': HEAD, 'ref': 'worker', 'repo': {'full_name': self.repository}},
                        'base': {'ref': 'main', 'repo': {'full_name': self.repository}}}
        self.calls = []
        self.runs = []
        self.fail = None

    def info(self):
        return {'default_branch': 'main'}

    def pr(self, number):
        return copy.deepcopy(self.current)

    def pages(self, path, key):
        return self.runs

    def dispatch(self, workflow, inputs):
        if workflow == self.fail:
            raise RuntimeError('transport failure')
        self.calls.append((workflow, inputs))


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = patch.object(cli, 'DB', Path(self.tmp.name) / 'fixture.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)
        self.client = Client()

    def queue(self):
        return cli.queue_pr_ci({}, self.client, self.client.pr(7), HEAD)

    def test_bot_pr_both_once_per_head_with_real_receipts(self):
        receipt = self.queue()
        self.queue()
        self.assertEqual([c[0] for c in self.client.calls], ['infrastructure-ci.yml', 'application-ci.yml'])
        self.assertEqual(receipt['pr'], 7)
        self.client.current['head']['sha'] = 'b' * 40
        cli.queue_pr_ci({}, self.client, self.client.pr(7), 'b' * 40)
        self.assertEqual(len(self.client.calls), 4)

    def test_partial_failure_replays_only_missing_workflow(self):
        self.client.fail = 'application-ci.yml'
        with self.assertRaises(RuntimeError):
            self.queue()
        self.assertEqual(cli.kv('ci-queued:' + HEAD)['workflows']['application-ci.yml'], 'pending')
        self.client.fail = None
        self.queue()
        self.queue()
        self.assertEqual(len(self.client.calls), 2)

    def test_accepted_dispatch_crash_recovers_visible_run(self):
        cli.kv('ci-queued:' + HEAD, {'pr': 7, 'workflows': {
            'infrastructure-ci.yml': 'dispatched', 'application-ci.yml': 'pending'}}, True)
        self.client.runs = [{'event': 'workflow_dispatch', 'head_branch': 'main',
            'repository': {'full_name': 'owner/repo'},
            'display_title': 'SDLC CI workflow_dispatch pr=7 sha=' + HEAD}]
        self.queue()
        self.assertEqual(self.client.calls, [])

    def test_stale_foreign_wrong_base_and_malformed_rejected(self):
        for change in ('head', 'repo', 'base', 'sha'):
            self.client = Client()
            if change == 'head': self.client.current['head']['sha'] = 'b' * 40
            if change == 'repo': self.client.current['head']['repo']['full_name'] = 'attacker/fork'
            if change == 'base': self.client.current['base']['ref'] = 'other'
            with self.assertRaises(ValueError):
                cli.queue_pr_ci({}, self.client, self.client.pr(7), 'bad' if change == 'sha' else HEAD)
            self.assertEqual(self.client.calls, [])

    def test_head_race_before_dispatch_rejected(self):
        pr = self.client.pr(7)
        self.client.current['head']['sha'] = 'b' * 40
        with self.assertRaises(ValueError):
            cli.queue_pr_ci({}, self.client, pr, HEAD)
        self.assertEqual(self.client.calls, [])

    def test_legacy_receipt_recovers_missing_dispatches(self):
        cli.kv('ci-queued:' + HEAD, {'pr': 7, 'time': 1}, True)
        self.queue()
        self.assertEqual(len(self.client.calls), 2)

    def test_workflow_contract(self):
        root = Path(__file__).resolve().parents[1]
        app = (root / '.github/workflows/application-ci.yml').read_text()
        names = ['application-lint', 'application-typecheck', 'application-unit-integration',
                 'application-e2e', 'application-build', 'application-i18n-security']
        operations = (root / 'docs/releases/R-1/OPERATIONS.md').read_text()
        for name in names:
            self.assertEqual(app.count('    name: ' + name + '\n'), 1)
            self.assertIn(name, operations)
        for script in ('lint', 'typecheck', 'test:unit', 'test:integration', 'test:e2e', 'build', 'check:i18n', 'check:security'):
            self.assertIn('pnpm ' + script + '\n', app)
        for workflow in ('application-ci.yml', 'infrastructure-ci.yml'):
            text = (root / '.github/workflows' / workflow).read_text()
            self.assertIn('workflow_dispatch:', text)
            self.assertIn('persist-credentials: false', text)
            self.assertIn('git rev-parse HEAD', text)
            self.assertNotIn('secrets.', text)
            self.assertNotIn('continue-on-error', text)
            self.assertNotIn('passWithNoTests', text)
            self.assertNotIn('contents: write', text)
            self.assertIn("assert pr['head']['sha'] == sha", text)
