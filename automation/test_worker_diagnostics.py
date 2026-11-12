"""Failure artifacts retain useful bounded reasons without credential values."""
import json
import tempfile
import unittest
from pathlib import Path

from automation.providers import build_prompt, sanitized_failure_report, validate_report


class WorkerDiagnostics(unittest.TestCase):
    def test_diagnostic_redacts_secrets_before_truncation_and_bounds_lists(self):
        secret = 'fixture-secret-value'
        report = {"summary": 'blocked ' + secret, "verdict": 'BLOCKED',
                  "findings": [{"id": str(i), "severity": 'high',
                                "description": secret + 'x' * 3000,
                                "reproduction": 'Bearer fixture-access-token'} for i in range(50)],
                  "evidence": ['sk-abcdefghijklmnop', 'ghp_abcdefghijklmnop'] * 50,
                  "limitations": [secret + 'z' * 3000] * 50}
        result = sanitized_failure_report(report, {'OPENAI_API_KEY': secret, 'PATH': '/fixture'})
        validate_report(result)
        text = json.dumps(result)
        self.assertNotIn(secret, text)
        self.assertNotIn('fixture-access-token', text)
        self.assertNotIn('abcdefghijklmnop', text)
        self.assertIn('[REDACTED]', text)
        self.assertLess(len(text), 50000)
        self.assertEqual(len(result['findings']), 8)
        self.assertEqual(len(result['limitations']), 12)
        self.assertEqual(report['summary'], 'blocked ' + secret)

    def test_prompt_explains_current_approval_and_correct_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'agents/roles').mkdir(parents=True)
            (root / 'agents/roles/devops.md').write_text('Trusted devops role')
            prompt = build_prompt(root, 'devops', {'founder_approval': 'founder', 'plan_hash': 'a' * 64})
            self.assertIn('supersedes older planning-only status snapshots', prompt)
            self.assertIn('return SUBMITTED for handoff', prompt)
            self.assertIn('requiring independent review and founder acceptance', prompt)
            self.assertIn('Do not mutate live policy, controller state', prompt)


if __name__ == '__main__':
    unittest.main()
