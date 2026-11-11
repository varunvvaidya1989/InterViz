"""Local fixture evidence for policy-only, started-release amendments."""
import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from automation.control import Control, ControlError


OLD = "a" * 64
NEW = "b" * 64
OTHER = "c" * 64
HEAD = "d" * 40
MERGE = "e" * 40
SCOPE = {"allowed_paths": ["automation/example.py"], "acceptance": ["Outcome"], "role": "devops"}
EVIDENCE = {"artifact": "fixture://amendment"}


class AmendmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.sqlite3"
        self.now = 1000.0
        self.control = self.reopen()
        self.control.create_release("R1", "Fixture release", "lead")
        self.control.upsert_story("R1", "S1", "Fixture story", SCOPE, [], "lead")
        self.control.submit_plan("R1", OLD, "lead")
        self.control.approve_plan("R1", OLD, "founder")

    def reopen(self):
        return Control(self.path, {"founder", "second-founder"}, clock=lambda: self.now)

    def amend(self, old=OLD, new=NEW, actor="founder"):
        return self.control.amend_plan("R1", old, new, actor)

    def assertCode(self, code, function, *args, **kwargs):
        before = self.tables()
        with self.assertRaises(ControlError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.tables(), before)

    def tables(self):
        with self.control._tx(False) as db:
            return {table: [dict(row) for row in db.execute("SELECT * FROM " + table)]
                    for table in ("releases", "items", "reviews", "ci_runs", "approvals", "events", "release_records")}

    def integrated(self):
        lease = self.control.claim("R1", "S1", "coder")
        self.control.associate_pr("R1", "S1", HEAD, "https://example.test/pr/1", "coder", "service", lease_id=lease["lease_id"])
        self.control.record_review("R1", "S1", HEAD, "reviewer", "APPROVE", EVIDENCE, "reviewer")
        self.control.record_ci("R1", "S1", HEAD, True, EVIDENCE, "ci")
        self.control.integrate("R1", "S1", HEAD, MERGE, "integrator")

    def frozen(self):
        self.integrated()
        self.control.start_qa("R1", MERGE, "qa")
        self.control.complete_qa("R1", MERGE, EVIDENCE, "qa")
        self.control.freeze_candidate("R1", MERGE, "lead")
        self.control.approve_release("R1", MERGE, "founder")

    def test_preserves_done_items_and_all_historical_evidence_clears_active_approvals(self):
        self.frozen()
        before = self.tables()
        result = self.amend()
        after = self.tables()
        for table in ("items", "reviews", "ci_runs", "approvals", "release_records"):
            self.assertEqual(after[table], before[table], table)
        self.assertEqual(after["events"][:-1], before["events"])
        self.assertEqual(after["events"][-1]["type"], "plan_amended")
        self.assertEqual(result["state"], "PLAN_SUBMITTED")
        self.assertEqual(result["plan_hash"], NEW)
        self.assertEqual(result["integration_sha"], MERGE)
        self.assertEqual(result["plan_scope_hash"], before["releases"][0]["plan_scope_hash"])
        for field in ("plan_approved_hash", "plan_approved_by", "qa_sha", "candidate_sha", "release_approved_sha", "release_approved_by"):
            self.assertIsNone(result[field], field)
        self.assertEqual(result["qa_passed"], 0)
        self.assertCode("stale_plan", self.control.approve_plan, "R1", OLD, "founder")
        self.assertCode("plan_not_approved", self.control.start_qa, "R1", MERGE, "qa")
        self.control.approve_plan("R1", NEW, "founder")
        self.control.start_qa("R1", MERGE, "qa")
        self.assertTrue(self.control.verify_audit()["valid"])

    def test_founder_required_including_replay_and_default_deny(self):
        self.assertCode("founder_required", self.amend, actor="worker")
        deny = Control(self.path)
        self.assertCode("founder_required", deny.amend_plan, "R1", OLD, NEW, "founder")
        self.amend()
        self.assertCode("founder_required", self.amend, actor="worker")

    def test_hash_validation_stale_cas_and_noop_rejected(self):
        self.assertCode("invalid_hash", self.amend, new="not-a-hash")
        self.assertCode("invalid_hash", self.amend, old="A" * 64)
        self.assertCode("invalid_amendment", self.amend, new=OLD)
        self.assertCode("stale_plan", self.amend, old=OTHER)
        self.amend()
        self.assertCode("stale_plan", self.amend, old=OTHER)
        self.assertCode("stale_plan", self.amend, actor="second-founder")
        self.assertCode("stale_plan", self.amend, new=OTHER)
        self.assertCode("plan_hash_reused", self.amend, old=NEW, new=OLD)

    def test_restart_replay_preserves_renewed_approval_and_emits_once(self):
        self.amend()
        self.control = self.reopen()
        self.control.approve_plan("R1", NEW, "founder")
        self.control.claim("R1", "S1", "coder")
        before = self.tables()
        self.amend()
        self.assertEqual(self.tables(), before)
        self.assertEqual(len([event for event in self.control.events() if event["type"] == "plan_amended"]), 1)

    def test_active_lease_rejected_expired_lease_preserved_and_dispatch_gated(self):
        self.control.claim("R1", "S1", "coder", lease_seconds=10)
        self.assertCode("lease_active", self.amend)
        self.now += 10
        before = self.tables()["items"]
        self.amend()
        self.assertEqual(self.tables()["items"], before)
        self.assertEqual(self.control.ready_items("R1"), [])
        self.assertCode("plan_not_approved", self.control.claim, "R1", "S1", "coder")
        self.control.approve_plan("R1", NEW, "founder")
        second = self.control.claim("R1", "S1", "coder")
        self.assertEqual(second["attempts"], 2)

    def test_changed_contract_or_dependency_rejected_even_if_hash_left_in_place(self):
        # Direct DB writes simulate a corrupt/stale import without allowing the
        # normal upsert invalidation to mask the scope comparison being tested.
        for field, value in (("title", "Changed"), ("scope", json.dumps({**SCOPE, "role": "coding"})),
                             ("scope", json.dumps({**SCOPE, "acceptance": ["Different"]})),
                             ("scope", json.dumps({**SCOPE, "allowed_paths": ["outside"]})),
                             ("depends_on", '["S2"]')):
            with self.subTest(field=field, value=value):
                with self.control._tx() as db:
                    original = db.execute("SELECT " + field + " FROM items WHERE id='S1'").fetchone()[0]
                    db.execute("UPDATE items SET " + field + "=? WHERE id='S1'", (value,))
                self.assertCode("missing_dependency" if field == "depends_on" else "scope_changed", self.amend)
                with self.control._tx() as db:
                    db.execute("UPDATE items SET " + field + "=? WHERE id='S1'", (original,))
        self.control.upsert_story("R1", "S2", "Additional item", SCOPE, ["S1"], "lead")
        self.assertCode("scope_changed", self.amend)

    def test_bug_lease_blocks_amendment_and_bug_rows_survive(self):
        self.integrated()
        self.control.start_qa("R1", MERGE, "qa")
        self.control.create_bug("R1", "B1", "Fixture bug", "qa", story_id="S1")
        self.control.claim("R1", "B1", "fixer", kind="bug", lease_seconds=10)
        self.assertCode("lease_active", self.amend)
        self.now += 11
        before = self.tables()["items"]
        self.amend()
        self.assertEqual(self.tables()["items"], before)

    def test_concurrent_cas_different_targets_has_one_winner(self):
        def attempt(new):
            try:
                return self.reopen().amend_plan("R1", OLD, new, "founder")["plan_hash"]
            except ControlError as error:
                return error.code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, (NEW, OTHER)))
        self.assertEqual(results.count("stale_plan"), 1)
        self.assertEqual(len([e for e in self.control.events() if e["type"] == "plan_amended"]), 1)
        self.assertTrue(self.control.verify_audit()["valid"])

    def test_concurrent_identical_replays_have_one_effect(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.reopen().amend_plan("R1", OLD, NEW, "founder"), range(2)))
        self.assertTrue(all(r["plan_hash"] == NEW for r in results))
        self.assertEqual(len([e for e in self.control.events() if e["type"] == "plan_amended"]), 1)

    def test_audit_failure_rolls_back_projection_and_event(self):
        before = self.tables()
        original = self.control._event

        def fail_after_event(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError("Fixture crash before commit")

        with patch.object(self.control, "_event", side_effect=fail_after_event):
            with self.assertRaises(RuntimeError):
                self.amend()
        self.assertEqual(self.tables(), before)
        self.amend()
        self.assertTrue(self.control.verify_audit()["valid"])

    def test_released_and_unsubmitted_releases_cannot_be_amended(self):
        self.frozen()
        self.control.record_release("R1", MERGE, "fixture-release", EVIDENCE, "operator")
        self.assertCode("release_immutable", self.amend)
        self.control.create_release("R2", "Draft", "lead")
        self.control.upsert_story("R2", "S1", "Fixture story", SCOPE, [], "lead")
        self.assertCode("scope_changed", self.control.amend_plan, "R2", OLD, NEW, "founder")


if __name__ == "__main__":
    unittest.main()
