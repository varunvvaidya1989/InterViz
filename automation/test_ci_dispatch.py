"""Bot dispatch recovery with durable isolated receipts; no GitHub access."""
import copy
from argparse import Namespace
from contextlib import ExitStack
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation import cli
from automation.github import GitHubError
from automation.test_application_ci import API, H


class DispatchAPI(API):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.fail = None
        self.fail_status = 422
        self.runs = {name: [] for name in self.runs}

    def dispatch(self, filename, inputs):
        if self.fail == filename:
            raise GitHubError('fixture dispatch unavailable', self.fail_status)
        self.calls.append((filename, inputs))
        self.runs[filename].append(dict(
            id=len(self.calls), workflow_id=1 if filename == 'infrastructure-ci.yml' else 2,
            display_title=f'SDLC CI workflow_dispatch pr=1 sha={H}',
            event='workflow_dispatch', head_branch='main',
            repository={'full_name': self.repository}))


class CIDispatch(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.db_patch = patch.object(cli, 'DB', Path(temp.name)/'state.sqlite3')
        self.db_patch.start(); self.addCleanup(self.db_patch.stop)
        out_patch = patch.object(cli, 'OUT', Path(temp.name)/'output')
        out_patch.start(); self.addCleanup(out_patch.stop)
        self.p = cli.policy(); self.p['repository']['full_name'] = API.repository
        self.api = DispatchAPI()
        self.item = {'head_sha': H}

    def queue(self):
        return cli.queue_ci(self.p, self.api, self.item, copy.deepcopy(self.api.pull))

    def test_bot_queues_both_once_per_head_with_pr_receipt(self):
        self.api.pull['user']['login'] = 'github-actions[bot]'
        self.assertEqual(self.queue(), ['infrastructure-ci.yml', 'application-ci.yml'])
        self.assertEqual(self.queue(), [])
        self.assertEqual(len(self.api.calls), 2)
        self.assertEqual(cli.kv('ci-queued:'+H)['pr'], 1)
        self.assertEqual(self.api.calls[0][1], {'pull-request': '1', 'revision': H})
        self.item['head_sha'] = 'c'*40
        self.api.pull['head']['sha'] = 'c'*40
        self.queue()
        self.assertEqual(len(self.api.calls), 4)

    def test_partial_dispatch_failure_recovers_only_missing_workflow(self):
        self.api.fail = 'application-ci.yml'
        with self.assertRaises(GitHubError): self.queue()
        self.assertTrue(cli.kv(f'ci-dispatch:1:{H}:infrastructure-ci.yml'))
        self.assertIsNone(cli.kv(f'ci-dispatch:1:{H}:application-ci.yml'))
        self.api.fail = None
        self.queue(); self.queue()
        self.assertEqual([name for name, _ in self.api.calls], ['infrastructure-ci.yml', 'application-ci.yml'])

    def test_missed_receipt_recovers_visible_run_without_duplicate(self):
        real_kv = cli.kv
        def crash(key, value=None, write=False):
            if write and key.startswith('ci-dispatch:') and key.endswith(':infrastructure-ci.yml'):
                raise RuntimeError('fixture process interruption after dispatch')
            return real_kv(key, value, write)
        with patch.object(cli, 'kv', side_effect=crash):
            with self.assertRaises(RuntimeError): self.queue()
        self.queue(); self.queue()
        self.assertEqual(len(self.api.calls), 2)
        self.assertTrue(cli.kv(f'ci-dispatch:1:{H}:infrastructure-ci.yml')['recovered'])

    def test_accepted_dispatch_with_lost_receipt_and_delayed_visibility_is_not_repeated(self):
        real_kv = cli.kv
        def crash(key, value=None, write=False):
            if write and key == f'ci-dispatch:1:{H}:infrastructure-ci.yml':
                raise RuntimeError('fixture interruption after accepted dispatch')
            return real_kv(key, value, write)
        with patch.object(cli, 'kv', side_effect=crash):
            with self.assertRaises(RuntimeError): self.queue()
        self.assertEqual(len(self.api.calls), 1)
        self.assertTrue(cli.kv(f'ci-dispatch-intent:1:{H}:infrastructure-ci.yml'))
        listing = self.api.pages
        def delayed(path, key=None):
            if '/infrastructure-ci.yml/runs' in path: return []
            return listing(path, key)
        with patch.object(self.api, 'pages', side_effect=delayed):
            self.queue(); self.queue()
        self.assertEqual([name for name, _ in self.api.calls],
                         ['infrastructure-ci.yml', 'application-ci.yml'])
        self.assertIsNone(cli.kv(f'ci-dispatch:1:{H}:infrastructure-ci.yml'))
        self.assertIn('WAITING_FOR_DISPATCH_EVIDENCE', (cli.OUT/'ci-dispatch-status.json').read_text())
        self.queue()
        self.assertEqual(len(self.api.calls), 2)
        self.assertTrue(cli.kv(f'ci-dispatch:1:{H}:infrastructure-ci.yml')['recovered'])

    def test_accepted_request_followed_by_transport_error_waits_for_evidence(self):
        dispatch = self.api.dispatch
        def accepted_then_error(filename, inputs):
            dispatch(filename, inputs)
            if filename == 'infrastructure-ci.yml':
                raise GitHubError('fixture response lost', 503)
        with patch.object(self.api, 'dispatch', side_effect=accepted_then_error):
            with self.assertRaises(GitHubError): self.queue()
        listing = self.api.pages
        with patch.object(self.api, 'pages', side_effect=lambda path, key=None:
                          [] if '/infrastructure-ci.yml/runs' in path else listing(path, key)):
            self.queue(); self.queue()
        self.assertEqual([name for name, _ in self.api.calls],
                         ['infrastructure-ci.yml', 'application-ci.yml'])
        self.queue()
        self.assertEqual(len(self.api.calls), 2)

    def test_interrupted_intent_without_visible_run_stays_blocked(self):
        cli.kv(f'ci-dispatch-intent:1:{H}:infrastructure-ci.yml',
               {'pr': 1, 'head': H, 'workflow_id': 1}, True)
        self.queue(); self.queue()
        self.assertEqual([name for name, _ in self.api.calls], ['application-ci.yml'])
        self.assertIsNone(cli.kv(f'ci-dispatch:1:{H}:infrastructure-ci.yml'))

    def test_reject_stale_fork_wrong_base_and_malformed_head_without_receipts(self):
        original = copy.deepcopy(self.api.pull)
        for mutate in (lambda p: p['head'].update(sha='d'*40),
                       lambda p: p['head']['repo'].update(full_name='other/repo'),
                       lambda p: p['base'].update(ref='other')):
            self.api.pull = copy.deepcopy(original); mutate(self.api.pull)
            with self.assertRaises(ValueError): self.queue()
        self.api.pull = original; self.item['head_sha'] = 'main;echo bad'
        with self.assertRaises(ValueError): self.queue()
        self.assertIsNone(cli.kv('ci-queued:'+H))
        self.assertEqual(self.api.calls, [])

    def test_head_changed_immediately_before_dispatch_rejected(self):
        original = self.api.pr
        calls = 0
        def changed(number):
            nonlocal calls
            calls += 1
            result = original(number)
            if calls > 1: result['head']['sha'] = 'e'*40
            return result
        with patch.object(self.api, 'pr', side_effect=changed):
            with self.assertRaises(ValueError): self.queue()
        self.assertEqual(self.api.calls, [])

    def test_legacy_queue_receipt_does_not_suppress_workflow_dispatch(self):
        cli.kv('ci-queued:'+H, {'pr': 1, 'time': 1}, True)
        self.queue()
        self.assertEqual(len(self.api.calls), 2)

    def test_scheduled_reconcile_recovers_missed_bot_pr_events(self):
        from automation.control import Control
        control = Control(cli.DB, {'founder'})
        control.create_release('R', 'fixture', 'lead')
        control.upsert_story('R', 'S', 'bootstrap',
                             {'kind': 'infrastructure', 'allowed_paths': ['automation/'],
                              'acceptance': ['dispatch']}, [], 'lead')
        control.submit_plan('R', 'a'*64, 'lead')
        control.approve_plan('R', 'a'*64, 'founder')
        lease = control.claim('R', 'S', 'github-actions[bot]')
        self.api.pull['user']['login'] = 'github-actions[bot]'
        control.associate_pr('R', 'S', H, self.api.pull['html_url'],
                             'github-actions[bot]', 'github', lease_id=lease['lease_id'])
        cli.kv('work-issue:R:story:S', 1, True)
        cli.kv('reviewed:R:story:S:'+H, True, True)
        pages = self.api.pages
        def listing(path, key=None):
            if '/issues?' in path: return []
            return pages(path, key)
        self.p['authority']['merge_enabled'] = False
        with ExitStack() as stack:
            for name, value in {
                'github': self.api, 'ledger': control, 'principal': 'founder',
                'replay_founder_commands': None, 'publish_result': None,
                'require_live': None, 'reconcile_pass_aliases': None,
                'finish_recovery_cache': None, 'recover_interrupted': [],
                'require_current_plan': ({}, 'a'*64), 'pr_files': ([], [])
            }.items():
                stack.enter_context(patch.object(cli, name, return_value=value))
            stack.enter_context(patch.object(cli, 'OUT', cli.DB.parent/'output'))
            stack.enter_context(patch.object(self.api, 'pages', side_effect=listing))
            cli.reconcile(self.p, Namespace(event_path=None))
            cli.reconcile(self.p, Namespace(event_path=None))
        self.assertEqual([name for name, _ in self.api.calls],
                         ['infrastructure-ci.yml', 'application-ci.yml'])



class WorkflowContract(unittest.TestCase):
    def test_six_jobs_commands_and_secret_free_trusted_definitions(self):
        root = Path(__file__).resolve().parents[1]
        app = (root/'.github/workflows/application-ci.yml').read_text()
        expected = {'application-lint': ['pnpm lint'], 'application-typecheck': ['pnpm typecheck'],
                    'application-unit-integration': ['pnpm test:unit', 'pnpm test:integration'],
                    'application-e2e': ['pnpm test:e2e'], 'application-build': ['pnpm build'],
                    'application-i18n-security': ['pnpm check:i18n', 'pnpm check:security']}
        for job, commands in expected.items():
            self.assertIn('  '+job+':\n', app)
            self.assertIn('    name: '+job+'\n', app)
            for command in commands: self.assertIn(command, app)
        self.assertIn("root.iter('testsuite')", app)
        for filename in ('application-ci.yml', 'infrastructure-ci.yml'):
            text = (root/'.github/workflows'/filename).read_text()
            self.assertIn('  workflow_dispatch:', text)
            self.assertNotIn('  pull_request:', text)
            self.assertNotIn('secrets.', text)
            self.assertNotIn('write\n', text)
            self.assertIn('persist-credentials: false', text)
            self.assertIn('test "$(git rev-parse HEAD)" = "$SDLC_TARGET_REVISION"', text)
            self.assertNotIn('continue-on-error', text)
        self.assertNotIn('passWithNoTests', app)


if __name__ == '__main__': unittest.main()
