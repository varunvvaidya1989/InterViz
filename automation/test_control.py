"""Infrastructure-only negative, revision, replay and concurrency checks."""
import concurrent.futures
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from automation.control import Control, ControlError


PLAN = "a" * 64
HEAD = "b" * 40
MERGE = "c" * 40
NEW = "d" * 40
SCOPE = {"allowed_paths": ["apps/web/"], "acceptance": ["A testable outcome"]}
EVIDENCE = {"artifact": "fixture://test", "result": "PASS"}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "ledger.sqlite3"
        self.now = [1000.0]
        self.control = Control(self.db, {"founder"}, clock=lambda: self.now[0], max_lease_seconds=1000)
        self.control.create_release("R1", "Infrastructure release", "lead")
        self.control.upsert_story("R1", "S1", "Scoped story", SCOPE, [], "lead")

    def assertCode(self, code, function, *args, **kwargs):
        with self.assertRaises(ControlError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def approved(self, plan=PLAN):
        self.control.submit_plan("R1", plan, "lead")
        self.control.approve_plan("R1", plan, "founder")

    def submitted(self, item_id="S1", kind="story", head=HEAD, worker="coder"):
        lease = self.control.claim("R1", item_id, worker, kind=kind)
        return self.control.associate_pr("R1", item_id, head, "https://example.test/pr/"+item_id, worker, "github-service", kind=kind, lease_id=lease["lease_id"])

    def integrated(self, item_id="S1", kind="story", head=HEAD, merge=MERGE, worker="coder"):
        self.submitted(item_id, kind, head, worker)
        self.control.record_review("R1", item_id, head, "reviewer", "APPROVE", EVIDENCE, "reviewer", kind=kind)
        self.control.record_ci("R1", item_id, head, True, EVIDENCE, "ci", kind=kind)
        return self.control.integrate("R1", item_id, head, merge, "integrator", kind=kind)

    def frozen(self):
        self.approved()
        self.integrated()
        self.control.start_qa("R1", MERGE, "qa")
        self.control.complete_qa("R1", MERGE, EVIDENCE, "qa")
        self.control.freeze_candidate("R1", MERGE, "lead")

    def test_plan_requires_allowlisted_founder_exact_hash_and_current_scope(self):
        self.assertCode("plan_not_approved", self.control.claim, "R1", "S1", "coder")
        self.control.submit_plan("R1", PLAN, "lead")
        self.assertCode("founder_required", self.control.approve_plan, "R1", PLAN, "model-consensus")
        self.assertCode("stale_plan", self.control.approve_plan, "R1", "e"*64, "founder")
        self.control.upsert_story("R1", "S2", "Another story", {"allowed_paths":["packages/ui"],"acceptance":["Accessible"]}, [], "lead")
        self.assertCode("stale_plan", self.control.approve_plan, "R1", PLAN, "founder")
        self.approved("e"*64)
        self.assertEqual(self.control.snapshot("R1")["releases"][0]["plan_approved_by"], "founder")

    def test_founder_can_request_revision_before_implementation(self):
        self.approved()
        self.assertCode("founder_required",self.control.request_plan_revision,"R1","Change scope","lead")
        self.control.request_plan_revision("R1","Change scope","founder")
        snapshot=self.control.snapshot("R1")
        self.assertEqual(snapshot["releases"][0]["state"],"DRAFT")
        self.assertIsNone(snapshot["releases"][0]["plan_approved_hash"])
        self.assertEqual(snapshot["items"],[])
        self.assertTrue(self.control.verify_audit()["valid"])

    def test_plan_revision_never_discards_started_work(self):
        self.approved();self.control.claim("R1","S1","coder")
        self.assertCode("implementation_started",self.control.request_plan_revision,"R1","Change scope","founder")

    def test_no_default_founder_and_duplicate_create_is_idempotent(self):
        before = len(self.control.events())
        self.control.create_release("R1", "Infrastructure release", "lead")
        self.assertEqual(len(self.control.events()), before)
        self.control.submit_plan("R1", PLAN, "lead")
        deny = Control(self.db)
        self.assertCode("founder_required", deny.approve_plan, "R1", PLAN, "founder")

    def test_cycle_and_missing_dependency_block_plan(self):
        self.control.upsert_story("R1", "S1", "Scoped story", SCOPE, ["S2"], "lead")
        self.assertCode("missing_dependency", self.control.submit_plan, "R1", PLAN, "lead")
        self.control.upsert_story("R1", "S2", "Scoped story 2", SCOPE, ["S1"], "lead")
        self.assertCode("dependency_cycle", self.control.submit_plan, "R1", PLAN, "lead")

    def test_dependency_integration_and_scope_leases(self):
        self.control.upsert_story("R1", "S2", "Dependent", SCOPE, ["S1"], "lead")
        self.control.upsert_story("R1", "S3", "Sibling", SCOPE, [], "lead")
        self.approved()
        self.assertCode("dependency_not_ready", self.control.claim, "R1", "S2", "coder-2")
        self.control.claim("R1", "S1", "coder")
        self.assertCode("scope_busy", self.control.claim, "R1", "S3", "coder-3")

    def test_lease_expiry_retries_and_total_heartbeat_bound(self):
        self.approved()
        first = self.control.claim("R1", "S1", "coder", lease_seconds=10)
        self.assertCode("lease_active", self.control.claim, "R1", "S1", "coder-2")
        self.now[0] += 11
        self.assertCode("lease_expired", self.control.heartbeat, first["lease_id"], "coder", 10)
        second = self.control.claim("R1", "S1", "coder-2", lease_seconds=10)
        self.assertEqual(second["attempts"], 2)
        self.assertCode("invalid_lease", self.control.associate_pr, "R1", "S1", HEAD, "https://example.test/pr/1", "coder", "github", lease_id=first["lease_id"])
        self.now[0] += 11
        self.assertCode("attempt_limit", self.control.claim, "R1", "S1", "coder-3")

    def test_concurrent_claim_has_one_winner(self):
        self.approved()
        def claim(worker):
            try:
                return self.control.claim("R1", "S1", worker)["lease_id"]
            except ControlError as error:
                return error.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, ["coder-1", "coder-2"]))
        self.assertEqual(results.count("lease_active"), 1)
        self.assertEqual(self.control.snapshot("R1")["items"][0]["attempts"], 1)

    def test_independent_review_ci_and_exact_head_are_required(self):
        self.approved(); self.submitted()
        self.assertCode("self_review", self.control.record_review, "R1", "S1", HEAD, "coder", "APPROVE", EVIDENCE, "coder")
        self.assertCode("identity_mismatch", self.control.record_review, "R1", "S1", HEAD, "reviewer", "APPROVE", EVIDENCE, "coder")
        self.assertCode("review_required", self.control.integrate, "R1", "S1", HEAD, MERGE, "lead")
        self.control.record_review("R1", "S1", HEAD, "reviewer", "APPROVE", EVIDENCE, "reviewer")
        self.assertCode("ci_required", self.control.integrate, "R1", "S1", HEAD, MERGE, "lead")
        self.assertCode("stale_head", self.control.record_ci, "R1", "S1", NEW, True, EVIDENCE, "ci")
        self.control.record_ci("R1", "S1", HEAD, True, EVIDENCE, "ci")
        self.control.associate_pr("R1", "S1", NEW, "https://example.test/pr/S1", "coder", "github")
        self.assertCode("stale_head", self.control.integrate, "R1", "S1", HEAD, MERGE, "lead")
        self.assertCode("review_required", self.control.integrate, "R1", "S1", NEW, MERGE, "lead")

    def test_new_head_invalidates_qa_frozen_candidate_and_founder_approval(self):
        self.frozen(); self.control.approve_release("R1", MERGE, "founder")
        self.control.associate_pr("R1", "S1", NEW, "https://example.test/pr/S1", "coder", "github")
        release = self.control.snapshot("R1")["releases"][0]
        self.assertIsNone(release["candidate_sha"])
        self.assertIsNone(release["release_approved_sha"])
        self.assertFalse(release["qa_passed"])
        self.assertCode("stale_candidate", self.control.complete_qa, "R1", MERGE, EVIDENCE, "qa")
        self.assertCode("unfinished_items", self.control.record_release, "R1", MERGE, "deploy-1", EVIDENCE, "devops")

    def test_request_changes_and_ci_failure_clear_release_gate(self):
        self.frozen(); self.control.approve_release("R1", MERGE, "founder")
        self.control.record_ci("R1", "S1", HEAD, False, {"artifact":"fixture://failed"}, "ci")
        release=self.control.snapshot("R1")["releases"][0]
        self.assertIsNone(release["release_approved_sha"])
        self.assertCode("ci_required", self.control.start_qa, "R1", MERGE, "qa")

    def test_bug_goes_to_developer_bucket_and_blocks_freeze(self):
        self.frozen()
        bug = self.control.create_bug("R1", "B1", "Failed keyboard interaction", "qa", story_id="S1", severity="high")
        self.assertTrue(bug["developer_bucket"])
        self.assertEqual(bug["developer_id"], "coder")
        self.assertCode("unfinished_items", self.control.freeze_candidate, "R1", MERGE, "lead")
        self.integrated("B1", "bug", NEW, "e"*40, "fixer")
        self.control.start_qa("R1", "e"*40, "qa")
        self.control.complete_qa("R1", "e"*40, EVIDENCE, "qa")
        reopened = self.control.reopen_bug("R1", "B1", "qa", "Regression found")
        self.assertTrue(reopened["developer_bucket"])
        self.assertEqual(reopened["status"], "OPEN")
        self.submitted("B1", "bug", NEW, "fixer")
        self.assertCode("review_required", self.control.integrate, "R1", "B1", NEW, "f"*40, "integrator", kind="bug")
        self.assertCode("scope_expansion", self.control.create_bug, "R1", "B2", "Unapproved feature", "qa", scope={"allowed_paths":["outside/"],"acceptance":["New feature"]})

    def test_qa_independent_and_candidate_exact(self):
        self.approved(); self.integrated()
        self.assertCode("stale_candidate", self.control.start_qa, "R1", NEW, "qa")
        self.control.start_qa("R1", MERGE, "qa")
        self.assertCode("self_qa", self.control.complete_qa, "R1", MERGE, EVIDENCE, "coder")
        self.assertCode("qa_required", self.control.freeze_candidate, "R1", MERGE, "lead")
        self.control.complete_qa("R1", MERGE, EVIDENCE, "qa")
        self.control.freeze_candidate("R1", MERGE, "lead")
        self.assertCode("founder_required", self.control.approve_release, "R1", MERGE, "lead")
        self.assertCode("stale_candidate", self.control.approve_release, "R1", NEW, "founder")

    def test_release_record_is_idempotent_and_released_projection_immutable(self):
        self.frozen()
        self.assertCode("release_not_approved", self.control.record_release, "R1", MERGE, "D1", EVIDENCE, "devops")
        self.control.approve_release("R1", MERGE, "founder")
        first = self.control.record_release("R1", MERGE, "D1", EVIDENCE, "devops")
        before = len(self.control.events())
        second = self.control.record_release("R1", MERGE, "D1", EVIDENCE, "devops")
        self.assertEqual(first, second)
        self.assertEqual(len(self.control.events()), before)
        self.assertCode("idempotency_conflict", self.control.record_release, "R1", NEW, "D1", EVIDENCE, "devops")
        self.assertCode("release_immutable", self.control.create_bug, "R1", "B1", "After release", "qa")

    def test_concurrent_head_update_never_retains_stale_founder_approval(self):
        self.frozen()
        def approve():
            try:
                self.control.approve_release("R1", MERGE, "founder")
                return "approved"
            except ControlError as error:
                return error.code
        def update():
            return self.control.associate_pr("R1", "S1", NEW, "https://example.test/pr/S1", "coder", "github")
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            approval = pool.submit(approve)
            update_result = pool.submit(update)
            self.assertIn(approval.result(), ("approved", "stale_candidate"))
            self.assertEqual(update_result.result()["head_sha"], NEW)
        release = self.control.snapshot("R1")["releases"][0]
        self.assertIsNone(release["release_approved_sha"])
        self.assertIsNone(release["candidate_sha"])

    def test_more_agent_approvals_cannot_override_unresolved_changes(self):
        self.approved(); self.submitted()
        self.control.record_ci("R1", "S1", HEAD, True, EVIDENCE, "ci")
        self.control.record_review("R1", "S1", HEAD, "reviewer", "REQUEST_CHANGES", EVIDENCE, "reviewer")
        for reviewer in ["review-2", "review-3", "review-4"]:
            self.control.record_review("R1", "S1", HEAD, reviewer, "APPROVE", EVIDENCE, reviewer)
        self.assertCode("review_required", self.control.integrate, "R1", "S1", HEAD, MERGE, "lead")

    def test_failed_transaction_leaves_no_partial_event_or_lease(self):
        self.approved()
        before = self.control.snapshot("R1")
        self.assertCode("invalid_lease", self.control.associate_pr, "R1", "S1", HEAD, "https://example.test/pr/S1", "coder", "github", lease_id="missing")
        self.assertEqual(before, self.control.snapshot("R1"))

    def test_audit_is_immutable_and_restart_is_durable(self):
        self.approved()
        restarted = Control(self.db, {"founder"}, clock=lambda:self.now[0])
        self.assertEqual(restarted.snapshot("R1"), self.control.snapshot("R1"))
        self.assertTrue(restarted.verify_audit()["valid"])
        with closing(sqlite3.connect(self.db)) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM events")
        self.assertTrue(restarted.verify_audit()["valid"])

    def test_amended_plan_revokes_old_worker_lease(self):
        self.approved()
        lease = self.control.claim("R1", "S1", "coder")
        self.control.upsert_story("R1", "S2", "New scope", {"allowed_paths":["packages/ui"],"acceptance":["Accessible UI"]}, [], "lead")
        self.assertCode("plan_hash_reused", self.control.submit_plan, "R1", PLAN, "lead")
        self.approved("e"*64)
        self.assertCode("invalid_lease", self.control.associate_pr, "R1", "S1", HEAD, "https://example.test/pr/S1", "coder", "github", lease_id=lease["lease_id"])

    def test_consistent_database_export_and_heartbeat_deadline(self):
        self.approved()
        lease = self.control.claim("R1", "S1", "coder", lease_seconds=900)
        self.now[0] += 800
        renewed = self.control.heartbeat(lease["lease_id"], "coder", 900)
        self.assertEqual(renewed["lease_until"], 2000)
        with closing(sqlite3.connect(":memory:")) as db:
            db.deserialize(self.control.export_database())
            self.assertEqual(db.execute("SELECT state FROM releases WHERE id='R1'").fetchone()[0], "BUILDING")

    def test_cli_json_errors_and_success(self):
        cmd=[sys.executable,"-m","automation.control","--db",str(self.db),"snapshot"]
        result=subprocess.run(cmd,input=json.dumps({"release_id":"R1"}),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        bad=subprocess.run(cmd,input='[]',capture_output=True,text=True)
        self.assertEqual(bad.returncode,2)
        self.assertEqual(json.loads(bad.stdout)["error"]["code"],"invalid_payload")


if __name__ == "__main__":
    unittest.main()
