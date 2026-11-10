"""Transactional, provider-independent founder SDLC ledger (Python standard library).

This infrastructure does not grant permission to implement the SaaS application.
Callers authenticate principals and authorize service/role capabilities separately;
``actor``/worker/reviewer IDs are verified identities, never model-supplied claims.
Founder IDs come from trusted constructor configuration and default to deny-all.

Scope format: {"allowed_paths": ["apps/web/"], "acceptance": ["..."], ...}.
Hashes are lowercase SHA-256 for plans and 40/64-character Git object IDs for heads.
Evidence is a nonempty JSON object describing external check artifacts. The ledger
enforces identity/revision/state gates; it does not pretend to execute CI or Git.

CLI: python -m automation.control --db state.sqlite3 --founders founder-id COMMAND
JSON payload is read from stdin or --payload. Output is one JSON object.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class ControlError(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}

    def as_dict(self):
        return {"code": self.code, "message": self.message, "details": self.details}


def _require(condition, code, message, **details):
    if not condition:
        raise ControlError(code, message, details)


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise ControlError("invalid_json", "Value must be finite JSON data.") from None


def _identity(value, label="identity"):
    _require(isinstance(value, str) and bool(value.strip()) and len(value) <= 200, "invalid_identity", f"Invalid {label}.")
    return value


def _sha(value, plan=False):
    pattern = r"[a-f0-9]{64}" if plan else r"(?:[a-f0-9]{40}|[a-f0-9]{64})"
    _require(isinstance(value, str) and re.fullmatch(pattern, value) is not None, "invalid_hash", "Expected a lowercase plan SHA-256 or Git object ID.")
    return value


def _scope(value):
    _require(isinstance(value, dict), "invalid_scope", "Scope must be an object.")
    result = json.loads(_json(value))
    for key in ("allowed_paths", "acceptance"):
        _require(isinstance(result.get(key), list) and bool(result[key]) and all(isinstance(v, str) and v.strip() for v in result[key]), "invalid_scope", f"Scope needs nonempty {key} strings.")
    paths = []
    for path in result["allowed_paths"]:
        path = path.replace("\\", "/").rstrip("/")
        _require(path and not path.startswith("/") and not re.match(r"^[A-Za-z]:", path) and all(part not in ("", ".", "..", ".git") for part in path.split("/")) and not any(c in path for c in "*?[]\x00"), "invalid_scope", "Paths must be relative literal file/directory prefixes.")
        paths.append(path)
    result["allowed_paths"] = sorted(set(paths))
    return result


def _evidence(value):
    _require(isinstance(value, dict) and bool(value), "invalid_evidence", "Evidence must be a nonempty JSON object.")
    return _json(value)


def _overlap(left, right):
    return any(a == b or a.startswith(b + "/") or b.startswith(a + "/") for a in left for b in right)


class Control:
    """Open a durable ledger. Connections are short-lived; mutations use BEGIN IMMEDIATE.

    Clock injection is for deterministic tests; production callers use the default
    clock. Do not let untrusted API payloads set founders, clock, or attempt limits.
    """

    def __init__(self, db_path, founder_ids=(), clock=None, max_attempts=2, max_lease_seconds=3600):
        self.path = Path(db_path)
        _require(str(db_path) != ":memory:", "invalid_database", "Use a file-backed SQLite ledger.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        _require(isinstance(founder_ids, (list, tuple, set, frozenset)), "invalid_founders", "Founder registry must be a trusted collection of identities.")
        self.founders = frozenset(_identity(x, "founder") for x in founder_ids)
        self.clock = clock or time.time
        _require(type(max_attempts) is int and 1 <= max_attempts <= 2, "invalid_limit", "Attempt limit must be 1 or 2.")
        _require(type(max_lease_seconds) in (int, float) and 0 < max_lease_seconds <= 86400, "invalid_limit", "Invalid maximum lease duration.")
        self.max_attempts, self.max_lease_seconds = max_attempts, float(max_lease_seconds)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS releases(
                  id TEXT PRIMARY KEY,title TEXT NOT NULL,metadata TEXT NOT NULL,state TEXT NOT NULL,
                  plan_hash TEXT,plan_scope_hash TEXT,plan_approved_hash TEXT,plan_approved_by TEXT,
                  integration_sha TEXT,qa_sha TEXT,qa_passed INTEGER NOT NULL DEFAULT 0,
                  candidate_sha TEXT,release_approved_sha TEXT,release_approved_by TEXT,
                  released_sha TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS items(
                  release_id TEXT NOT NULL REFERENCES releases(id),kind TEXT NOT NULL,id TEXT NOT NULL,
                  title TEXT NOT NULL,scope TEXT NOT NULL,depends_on TEXT NOT NULL,status TEXT NOT NULL,
                  author_ids TEXT NOT NULL DEFAULT '[]',head_sha TEXT,pr_url TEXT,integration_sha TEXT,
                  epoch INTEGER NOT NULL DEFAULT 0,attempts INTEGER NOT NULL DEFAULT 0,max_attempts INTEGER NOT NULL,
                  lease_id TEXT,lease_worker TEXT,lease_until REAL,lease_started REAL,
                  parent_story TEXT,developer_id TEXT,severity TEXT,created_at REAL NOT NULL,updated_at REAL NOT NULL,
                  PRIMARY KEY(release_id,kind,id));
                CREATE UNIQUE INDEX IF NOT EXISTS unique_active_lease ON items(lease_id) WHERE lease_id IS NOT NULL;
                CREATE TABLE IF NOT EXISTS reviews(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT,release_id TEXT NOT NULL,kind TEXT NOT NULL,item_id TEXT NOT NULL,
                  head_sha TEXT NOT NULL,epoch INTEGER NOT NULL,reviewer_id TEXT NOT NULL,verdict TEXT NOT NULL,
                  evidence TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS ci_runs(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT,release_id TEXT NOT NULL,kind TEXT NOT NULL,item_id TEXT NOT NULL,
                  head_sha TEXT NOT NULL,epoch INTEGER NOT NULL,passed INTEGER NOT NULL,evidence TEXT NOT NULL,
                  actor TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS approvals(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT,release_id TEXT NOT NULL,kind TEXT NOT NULL,
                  target_hash TEXT NOT NULL,actor TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS release_records(
                  idempotency_key TEXT PRIMARY KEY,release_id TEXT UNIQUE NOT NULL,released_sha TEXT NOT NULL,
                  payload_hash TEXT NOT NULL,evidence TEXT NOT NULL,actor TEXT NOT NULL,created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS events(
                  seq INTEGER PRIMARY KEY AUTOINCREMENT,release_id TEXT NOT NULL,type TEXT NOT NULL,
                  actor TEXT NOT NULL,payload TEXT NOT NULL,created_at REAL NOT NULL,
                  previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL);
            """)
            for table in ("reviews", "ci_runs", "approvals", "release_records", "events"):
                for verb in ("UPDATE", "DELETE"):
                    db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{verb.lower()} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT,'immutable ledger record'); END")

    @contextmanager
    def _connection(self):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=15000")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _tx(self, write=True):
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _release(self, db, release_id, mutable=False):
        _identity(release_id, "release ID")
        row = db.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
        _require(row is not None, "not_found", "Release not found.")
        _require(not mutable or row["state"] != "RELEASED", "release_immutable", "Released records are immutable; create another release.")
        return dict(row)

    def _item(self, db, release_id, item_id, kind="story"):
        _require(kind in ("story", "bug"), "invalid_kind", "Item kind must be story or bug.")
        row = db.execute("SELECT * FROM items WHERE release_id=? AND kind=? AND id=?", (release_id, kind, item_id)).fetchone()
        _require(row is not None, "not_found", "Work item not found.")
        return dict(row)

    def _event(self, db, release_id, event, actor, payload):
        _identity(actor)
        now = float(self.clock())
        previous = db.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
        previous = previous[0] if previous else "0" * 64
        raw = _json({"release_id": release_id, "type": event, "actor": actor, "payload": payload, "created_at": now, "previous_hash": previous})
        digest = hashlib.sha256(raw.encode()).hexdigest()
        db.execute("INSERT INTO events(release_id,type,actor,payload,created_at,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)", (release_id, event, actor, _json(payload), now, previous, digest))
        db.execute("UPDATE releases SET updated_at=? WHERE id=?", (now, release_id))

    def _founder(self, actor):
        _identity(actor)
        _require(actor in self.founders, "founder_required", "A trusted allowlisted founder identity is required.")

    def _approved(self, release):
        _require(release["plan_hash"] and release["plan_approved_hash"] == release["plan_hash"], "plan_not_approved", "The current exact plan needs founder approval.")

    def _invalidate(self, db, release_id, state="BUILDING", plan=False):
        sql = "UPDATE releases SET state=?,qa_sha=NULL,qa_passed=0,candidate_sha=NULL,release_approved_sha=NULL,release_approved_by=NULL"
        if plan:
            sql += ",plan_hash=NULL,plan_scope_hash=NULL,plan_approved_hash=NULL,plan_approved_by=NULL"
            # A prior job cannot submit under an amended plan's later approval.
            db.execute("UPDATE items SET status=CASE WHEN status='IN_PROGRESS' THEN 'OPEN' ELSE status END,lease_id=NULL,lease_worker=NULL,lease_until=NULL WHERE release_id=?", (release_id,))
        db.execute(sql + " WHERE id=?", (state, release_id))

    def _scope_hash(self, db, release_id):
        rows = db.execute("SELECT id,title,scope,depends_on FROM items WHERE release_id=? AND kind='story' ORDER BY id", (release_id,)).fetchall()
        _require(rows, "empty_release", "A release plan needs at least one scoped story.")
        stories = {r["id"]: dict(r) for r in rows}
        visiting, visited = set(), set()

        def visit(item_id):
            _require(item_id in stories, "missing_dependency", "Story dependency is absent.", dependency=item_id)
            _require(item_id not in visiting, "dependency_cycle", "Story dependencies contain a cycle.")
            if item_id in visited:
                return
            visiting.add(item_id)
            for dep in json.loads(stories[item_id]["depends_on"]):
                visit(dep)
            visiting.remove(item_id)
            visited.add(item_id)

        for item_id in stories:
            visit(item_id)
        return hashlib.sha256(_json([dict(r) for r in rows]).encode()).hexdigest()

    @staticmethod
    def _decoded(row):
        result = dict(row)
        for key in ("scope", "depends_on", "author_ids", "metadata", "evidence", "payload"):
            if key in result:
                result[key] = json.loads(result[key])
        if "kind" in result:
            result["developer_bucket"] = result["kind"] == "bug" and result.get("status") not in ("INTEGRATED", "DONE")
        return result

    def create_release(self, release_id, title, actor, metadata=None):
        _identity(release_id, "release ID"); _identity(title, "title"); _identity(actor)
        metadata = _json(metadata or {})
        with self._tx() as db:
            old = db.execute("SELECT * FROM releases WHERE id=?", (release_id,)).fetchone()
            if old:
                _require(old["title"] == title and old["metadata"] == metadata, "conflict", "Release ID already has different contents.")
                return self._decoded(old)
            now = float(self.clock())
            db.execute("INSERT INTO releases(id,title,metadata,state,created_at,updated_at) VALUES(?,?,?,'DRAFT',?,?)", (release_id, title, metadata, now, now))
            self._event(db, release_id, "release_created", actor, {"title": title})
            return self._decoded(self._release(db, release_id))

    def upsert_story(self, release_id, story_id, title, scope, depends_on, actor):
        _identity(story_id, "story ID"); _identity(title, "title"); _identity(actor)
        scope = _scope(scope)
        _require(isinstance(depends_on, list) and all(isinstance(d, str) and d for d in depends_on), "invalid_dependencies", "Dependencies must be story ID strings.")
        deps = sorted(set(depends_on))
        _require(story_id not in deps, "dependency_cycle", "A story cannot depend on itself.")
        with self._tx() as db:
            self._release(db, release_id, True)
            old = db.execute("SELECT * FROM items WHERE release_id=? AND kind='story' AND id=?", (release_id, story_id)).fetchone()
            if old and old["title"] == title and old["scope"] == _json(scope) and old["depends_on"] == _json(deps):
                return self._decoded(old)
            if old:
                _require(not old["lease_until"] or old["lease_until"] <= self.clock(), "lease_active", "Cannot change scope while a worker owns its lease.")
                db.execute("UPDATE items SET title=?,scope=?,depends_on=?,status='OPEN',head_sha=NULL,integration_sha=NULL,epoch=epoch+1,lease_id=NULL,lease_worker=NULL,lease_until=NULL,updated_at=? WHERE release_id=? AND kind='story' AND id=?", (title, _json(scope), _json(deps), self.clock(), release_id, story_id))
            else:
                db.execute("INSERT INTO items(release_id,kind,id,title,scope,depends_on,status,max_attempts,created_at,updated_at) VALUES(?,'story',?,?,?,?,'OPEN',?,?,?)", (release_id, story_id, title, _json(scope), _json(deps), self.max_attempts, self.clock(), self.clock()))
            self._invalidate(db, release_id, "DRAFT", plan=True)
            self._event(db, release_id, "story_scoped", actor, {"story_id": story_id, "scope": scope, "depends_on": deps})
            return self._decoded(self._item(db, release_id, story_id))

    def submit_plan(self, release_id, plan_hash, actor):
        _sha(plan_hash, plan=True)
        with self._tx() as db:
            release = self._release(db, release_id, True)
            scope_hash = self._scope_hash(db, release_id)
            previous = db.execute("SELECT payload FROM events WHERE release_id=? AND type='plan_submitted'", (release_id,)).fetchall()
            for record in previous:
                submitted = json.loads(record["payload"])
                _require(submitted["plan_hash"] != plan_hash or submitted["scope_hash"] == scope_hash, "plan_hash_reused", "One plan hash cannot identify different scoped stories; hash the new manifest.")
            if release["plan_hash"] == plan_hash and release["plan_scope_hash"] == scope_hash:
                return self._decoded(release)
            self._invalidate(db, release_id, "PLAN_SUBMITTED", plan=True)
            db.execute("UPDATE releases SET plan_hash=?,plan_scope_hash=? WHERE id=?", (plan_hash, scope_hash, release_id))
            self._event(db, release_id, "plan_submitted", actor, {"plan_hash": plan_hash, "scope_hash": scope_hash})
            return self._decoded(self._release(db, release_id))

    def amend_plan(self, release_id, expected_old_hash, new_hash, actor):
        """Replace a plan hash without rewriting any started work.

        The trusted caller authenticates actor and verifies the new canonical
        manifest has identical item contracts/dependencies before calling. Hashes
        alone cannot prove manifest contents. Here the submitted scope snapshot
        must still match the ledger. No approval is carried to the new hash.
        """
        self._founder(actor)
        _sha(expected_old_hash, plan=True); _sha(new_hash, plan=True)
        _require(expected_old_hash != new_hash, "invalid_amendment", "An amendment needs a different plan hash.")
        with self._tx() as db:
            release = self._release(db, release_id, True)
            scope_hash = self._scope_hash(db, release_id)
            _require(release["plan_scope_hash"] == scope_hash, "scope_changed", "Amendment cannot change item contracts or dependencies.")
            # Only the current, previously committed transition is a replay.
            # In particular, an arbitrary stale CAS targeting the current hash
            # must not be mistaken for a successful amendment.
            if release["plan_hash"] == new_hash:
                previous = db.execute("SELECT payload FROM events WHERE release_id=? AND type='plan_amended' ORDER BY seq DESC LIMIT 1", (release_id,)).fetchone()
                if previous:
                    payload = json.loads(previous["payload"])
                    if payload == {"expected_old_hash": expected_old_hash, "new_hash": new_hash, "scope_hash": scope_hash, "actor": actor}:
                        return self._decoded(release)
            _require(release["plan_hash"] == expected_old_hash, "stale_plan", "Amendment must compare against the current exact plan hash.")
            _require(not db.execute("SELECT 1 FROM items WHERE release_id=? AND lease_until>?", (release_id, self.clock())).fetchone(), "lease_active", "Cannot amend a plan while a worker owns an active lease.")
            # Prevent hash reuse (ABA) from making an old approval or CAS current.
            for row in db.execute("SELECT type,payload FROM events WHERE release_id=? AND type IN ('plan_submitted','plan_amended')", (release_id,)):
                payload = json.loads(row["payload"])
                historical_hash = payload["plan_hash"] if row["type"] == "plan_submitted" else payload["new_hash"]
                _require(new_hash != historical_hash, "plan_hash_reused", "Amendments require a fresh canonical plan hash.")
            self._invalidate(db, release_id, "PLAN_SUBMITTED")
            db.execute("UPDATE releases SET plan_hash=?,plan_approved_hash=NULL,plan_approved_by=NULL WHERE id=?", (new_hash, release_id))
            self._event(db, release_id, "plan_amended", actor, {"expected_old_hash": expected_old_hash, "new_hash": new_hash, "scope_hash": scope_hash, "actor": actor})
            return self._decoded(self._release(db, release_id))

    def approve_plan(self, release_id, plan_hash, actor):
        self._founder(actor); _sha(plan_hash, plan=True)
        with self._tx() as db:
            release = self._release(db, release_id, True)
            _require(plan_hash == release["plan_hash"] and self._scope_hash(db, release_id) == release["plan_scope_hash"], "stale_plan", "Approval must match the submitted plan and scoped stories exactly.")
            if release["plan_approved_hash"] == plan_hash:
                return self._decoded(release)
            db.execute("UPDATE releases SET state='PLAN_APPROVED',plan_approved_hash=?,plan_approved_by=? WHERE id=?", (plan_hash, actor, release_id))
            db.execute("INSERT INTO approvals(release_id,kind,target_hash,actor,created_at) VALUES(?,'plan',?,?,?)", (release_id, plan_hash, actor, self.clock()))
            self._event(db, release_id, "plan_approved", actor, {"plan_hash": plan_hash})
            return self._decoded(self._release(db, release_id))

    def request_plan_revision(self, release_id, feedback, actor):
        self._founder(actor)
        _require(isinstance(feedback,str) and feedback.strip(), "feedback_required", "Describe the requested plan changes.")
        with self._tx() as db:
            self._release(db,release_id,True)
            _require(not db.execute("SELECT 1 FROM items WHERE release_id=? AND attempts>0",(release_id,)).fetchone(), "implementation_started", "Started releases need an explicit amendment plan; do not discard their work.")
            self._invalidate(db,release_id,"DRAFT",plan=True)
            db.execute("DELETE FROM items WHERE release_id=?",(release_id,))
            self._event(db,release_id,"plan_revision_requested",actor,{"feedback":feedback})
            return self._decoded(self._release(db,release_id))

    def _lease_seconds(self, value):
        _require(type(value) in (int, float) and 0 < value <= self.max_lease_seconds, "invalid_lease", "Lease duration exceeds its configured bound.")
        return float(value)

    def claim(self, release_id, item_id, worker_id, kind="story", lease_seconds=900):
        _identity(worker_id, "worker"); duration = self._lease_seconds(lease_seconds)
        with self._tx() as db:
            release = self._release(db, release_id, True); self._approved(release)
            item = self._item(db, release_id, item_id, kind)
            now = float(self.clock())
            _require(not item["lease_until"] or item["lease_until"] <= now, "lease_active", "The work item has a live lease.")
            _require(item["status"] == "OPEN" or (item["status"] == "IN_PROGRESS" and item["lease_until"] <= now), "not_claimable", "Only open or interrupted work can be claimed.")
            _require(item["attempts"] < item["max_attempts"], "attempt_limit", "The item exhausted its bounded attempts; lead decomposition is required.")
            for dep in json.loads(item["depends_on"]):
                _require(self._item(db, release_id, dep)["status"] in ("INTEGRATED", "DONE"), "dependency_not_ready", "A dependency has not been independently accepted and integrated.", dependency=dep)
            paths = json.loads(item["scope"])["allowed_paths"]
            for lease in db.execute("SELECT scope,id,release_id FROM items WHERE lease_until>?", (now,)):
                _require(not _overlap(paths, json.loads(lease["scope"])["allowed_paths"]), "scope_busy", "Another active lease owns an overlapping path.", item_id=lease["id"])
            lease_id = uuid.uuid4().hex
            db.execute("UPDATE items SET status='IN_PROGRESS',attempts=attempts+1,epoch=epoch+1,head_sha=NULL,integration_sha=NULL,lease_id=?,lease_worker=?,lease_until=?,lease_started=?,developer_id=?,updated_at=? WHERE release_id=? AND kind=? AND id=?", (lease_id, worker_id, now+duration, now, worker_id, now, release_id, kind, item_id))
            self._invalidate(db, release_id)
            self._event(db, release_id, "item_claimed", worker_id, {"kind": kind, "item_id": item_id, "lease_id": lease_id, "until": now+duration})
            return self._decoded(self._item(db, release_id, item_id, kind))

    def heartbeat(self, lease_id, worker_id, lease_seconds=900):
        duration = self._lease_seconds(lease_seconds)
        with self._tx() as db:
            row = db.execute("SELECT * FROM items WHERE lease_id=?", (lease_id,)).fetchone()
            _require(row is not None and row["lease_worker"] == worker_id, "invalid_lease", "Lease identity does not match.")
            now = float(self.clock())
            _require(row["lease_until"] > now, "lease_expired", "An expired lease cannot be renewed.")
            until = min(now+duration, row["lease_started"]+self.max_lease_seconds)
            _require(until > now, "lease_expired", "The total attempt duration is exhausted.")
            db.execute("UPDATE items SET lease_until=? WHERE lease_id=?", (until, lease_id))
            self._event(db, row["release_id"], "lease_renewed", worker_id, {"lease_id": lease_id, "until": until})
            return {"lease_id": lease_id, "lease_until": until}

    def associate_pr(self, release_id, item_id, head_sha, pr_url, author_id, actor, kind="story", lease_id=None):
        _sha(head_sha); _identity(author_id, "PR author")
        _require(isinstance(pr_url, str) and re.fullmatch(r"https://[^\s]+", pr_url) is not None, "invalid_pr", "PR association requires an HTTPS provider URL.")
        with self._tx() as db:
            release = self._release(db, release_id, True); self._approved(release)
            item = self._item(db, release_id, item_id, kind)
            if item["head_sha"] == head_sha and item["pr_url"] == pr_url:
                return self._decoded(item)
            if not item["pr_url"] or not item["head_sha"]:
                _require(lease_id and lease_id == item["lease_id"] and item["lease_worker"] == author_id and item["lease_until"] > self.clock(), "invalid_lease", "First PR submission requires its author's live task lease.")
            else:
                _require(item["pr_url"] == pr_url, "pr_conflict", "A work item cannot silently switch its associated PR.")
            authors = sorted(set(json.loads(item["author_ids"]) + [author_id]))
            db.execute("UPDATE items SET status='SUBMITTED',author_ids=?,head_sha=?,pr_url=?,integration_sha=NULL,epoch=epoch+1,lease_id=NULL,lease_worker=NULL,lease_until=NULL,updated_at=? WHERE release_id=? AND kind=? AND id=?", (_json(authors), head_sha, pr_url, self.clock(), release_id, kind, item_id))
            self._invalidate(db, release_id)
            self._event(db, release_id, "pr_head_associated", actor, {"kind": kind, "item_id": item_id, "head_sha": head_sha, "author_id": author_id, "pr_url": pr_url})
            return self._decoded(self._item(db, release_id, item_id, kind))

    def record_review(self, release_id, item_id, head_sha, reviewer_id, verdict, evidence, actor, kind="story"):
        _sha(head_sha); raw = _evidence(evidence); _identity(reviewer_id, "reviewer")
        _require(verdict in ("APPROVE", "REQUEST_CHANGES"), "invalid_verdict", "Review verdict must be APPROVE or REQUEST_CHANGES.")
        _require(actor == reviewer_id, "identity_mismatch", "Review actor must be the verified reviewer identity.")
        with self._tx() as db:
            self._release(db, release_id, True)
            item = self._item(db, release_id, item_id, kind)
            _require(item["head_sha"] == head_sha, "stale_head", "Review must target the current exact PR head.")
            _require(reviewer_id not in json.loads(item["author_ids"]), "self_review", "A coding author cannot independently review its own item.")
            db.execute("INSERT INTO reviews(release_id,kind,item_id,head_sha,epoch,reviewer_id,verdict,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (release_id, kind, item_id, head_sha, item["epoch"], reviewer_id, verdict, raw, self.clock()))
            if verdict == "REQUEST_CHANGES":
                db.execute("UPDATE items SET status='OPEN',integration_sha=NULL WHERE release_id=? AND kind=? AND id=?", (release_id, kind, item_id))
                self._invalidate(db, release_id)
            self._event(db, release_id, "review_recorded", actor, {"kind": kind, "item_id": item_id, "head_sha": head_sha, "verdict": verdict, "evidence": evidence})
            return {"head_sha": head_sha, "verdict": verdict}

    def record_ci(self, release_id, item_id, head_sha, passed, evidence, actor, kind="story"):
        _sha(head_sha); raw = _evidence(evidence)
        _require(type(passed) is bool, "invalid_result", "CI passed must be a boolean.")
        with self._tx() as db:
            self._release(db, release_id, True)
            item = self._item(db, release_id, item_id, kind)
            _require(item["head_sha"] == head_sha, "stale_head", "CI must target the current exact PR head.")
            db.execute("INSERT INTO ci_runs(release_id,kind,item_id,head_sha,epoch,passed,evidence,actor,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (release_id, kind, item_id, head_sha, item["epoch"], int(passed), raw, actor, self.clock()))
            if not passed:
                self._invalidate(db, release_id)
            self._event(db, release_id, "ci_recorded", actor, {"kind": kind, "item_id": item_id, "head_sha": head_sha, "passed": passed, "evidence": evidence})
            return {"head_sha": head_sha, "passed": passed}

    def _pr_ready(self, db, item):
        args = (item["release_id"], item["kind"], item["id"], item["head_sha"], item["epoch"])
        _require(item["head_sha"] is not None, "pr_required", "A current PR head is required.")
        reviews = db.execute("SELECT reviewer_id,verdict FROM reviews WHERE release_id=? AND kind=? AND item_id=? AND head_sha=? AND epoch=? ORDER BY seq", args).fetchall()
        latest = {r["reviewer_id"]: r["verdict"] for r in reviews}
        _require("APPROVE" in latest.values() and "REQUEST_CHANGES" not in latest.values(), "review_required", "Current head needs independent approval without unresolved change requests.")
        ci = db.execute("SELECT passed FROM ci_runs WHERE release_id=? AND kind=? AND item_id=? AND head_sha=? AND epoch=? ORDER BY seq DESC LIMIT 1", args).fetchone()
        _require(ci is not None and bool(ci["passed"]), "ci_required", "Current head needs successful latest CI evidence.")

    def integrate(self, release_id, item_id, head_sha, integration_sha, actor, kind="story"):
        _sha(head_sha); _sha(integration_sha)
        with self._tx() as db:
            release = self._release(db, release_id, True); self._approved(release)
            item = self._item(db, release_id, item_id, kind)
            _require(item["head_sha"] == head_sha, "stale_head", "Integration must target the reviewed exact head.")
            self._pr_ready(db, item)
            _require(item["status"] in ("SUBMITTED", "INTEGRATED", "DONE"), "invalid_stage", "The item is not submitted for integration.")
            if item["integration_sha"] == integration_sha and release["integration_sha"] == integration_sha:
                return self._decoded(item)
            db.execute("UPDATE items SET status='INTEGRATED',integration_sha=?,updated_at=? WHERE release_id=? AND kind=? AND id=?", (integration_sha, self.clock(), release_id, kind, item_id))
            self._invalidate(db, release_id)
            db.execute("UPDATE releases SET integration_sha=? WHERE id=?", (integration_sha, release_id))
            self._event(db, release_id, "item_integrated", actor, {"kind": kind, "item_id": item_id, "head_sha": head_sha, "integration_sha": integration_sha})
            return self._decoded(self._item(db, release_id, item_id, kind))

    def _integrated(self, db, release_id):
        items = [dict(r) for r in db.execute("SELECT * FROM items WHERE release_id=?", (release_id,))]
        _require(any(i["kind"] == "story" for i in items), "empty_release", "A release needs stories.")
        _require(all(i["status"] in ("INTEGRATED", "DONE") for i in items), "unfinished_items", "All stories and bugs must be integrated before QA.")
        for item in items:
            self._pr_ready(db, item)
        return items

    def start_qa(self, release_id, candidate_sha, actor):
        _sha(candidate_sha)
        with self._tx() as db:
            release = self._release(db, release_id, True); self._approved(release)
            _require(release["integration_sha"] == candidate_sha, "stale_candidate", "QA must use the current integrated revision.")
            self._integrated(db, release_id)
            self._invalidate(db, release_id, "QA")
            db.execute("UPDATE releases SET qa_sha=? WHERE id=?", (candidate_sha, release_id))
            self._event(db, release_id, "qa_started", actor, {"candidate_sha": candidate_sha})
            return self._decoded(self._release(db, release_id))

    def create_bug(self, release_id, bug_id, title, actor, scope=None, story_id=None, severity="normal", developer_id=None):
        _identity(bug_id, "bug ID"); _identity(title, "bug title")
        _require(severity in ("low", "normal", "high", "critical"), "invalid_severity", "Invalid severity.")
        with self._tx() as db:
            self._release(db, release_id, True)
            parent = self._item(db, release_id, story_id) if story_id else None
            stories = list(db.execute("SELECT scope FROM items WHERE release_id=? AND kind='story'", (release_id,)))
            allowed = [p for s in stories for p in json.loads(s["scope"])["allowed_paths"]]
            if scope is None:
                scope = json.loads(parent["scope"]) if parent else {"allowed_paths": allowed, "acceptance": [title]}
            scope = _scope(scope)
            _require(all(any(p == a or p.startswith(a + "/") for a in allowed) for p in scope["allowed_paths"]), "scope_expansion", "A bug fix cannot expand the approved story path scope; amend the plan first.")
            old = db.execute("SELECT * FROM items WHERE release_id=? AND kind='bug' AND id=?", (release_id, bug_id)).fetchone()
            if old:
                _require(old["title"] == title and old["scope"] == _json(scope) and old["parent_story"] == story_id, "conflict", "Bug ID already has different contents; reopen it explicitly.")
                return self._decoded(old)
            developer_id = developer_id or (parent["developer_id"] if parent else None)
            db.execute("INSERT INTO items(release_id,kind,id,title,scope,depends_on,status,max_attempts,parent_story,developer_id,severity,created_at,updated_at) VALUES(?,'bug',?,?,?,'[]','OPEN',?,?,?,?,?,?)", (release_id, bug_id, title, _json(scope), self.max_attempts, story_id, developer_id, severity, self.clock(), self.clock()))
            self._invalidate(db, release_id)
            self._event(db, release_id, "bug_created", actor, {"bug_id": bug_id, "story_id": story_id, "developer_id": developer_id, "severity": severity})
            return self._decoded(self._item(db, release_id, bug_id, "bug"))

    def reopen_bug(self, release_id, bug_id, actor, reason):
        _identity(reason, "reopen reason")
        with self._tx() as db:
            self._release(db, release_id, True)
            item = self._item(db, release_id, bug_id, "bug")
            _require(not item["lease_until"] or item["lease_until"] <= self.clock(), "lease_active", "Cannot reopen a leased bug.")
            db.execute("UPDATE items SET status='OPEN',head_sha=NULL,integration_sha=NULL,epoch=epoch+1,lease_id=NULL,lease_worker=NULL,lease_until=NULL,updated_at=? WHERE release_id=? AND kind='bug' AND id=?", (self.clock(), release_id, bug_id))
            self._invalidate(db, release_id)
            self._event(db, release_id, "bug_reopened", actor, {"bug_id": bug_id, "reason": reason})
            return self._decoded(self._item(db, release_id, bug_id, "bug"))

    def complete_qa(self, release_id, candidate_sha, evidence, actor):
        _sha(candidate_sha); raw = _evidence(evidence)
        with self._tx() as db:
            release = self._release(db, release_id, True); self._approved(release)
            _require(release["state"] == "QA" and release["qa_sha"] == candidate_sha == release["integration_sha"], "stale_candidate", "QA completion must target the active exact integrated QA revision.")
            items = self._integrated(db, release_id)
            _require(all(actor not in json.loads(i["author_ids"]) for i in items), "self_qa", "A coding author cannot certify independent release QA.")
            db.execute("UPDATE items SET status='DONE' WHERE release_id=?", (release_id,))
            db.execute("UPDATE releases SET state='QA_PASSED',qa_passed=1 WHERE id=?", (release_id,))
            self._event(db, release_id, "qa_completed", actor, {"candidate_sha": candidate_sha, "evidence": json.loads(raw)})
            return self._decoded(self._release(db, release_id))

    def freeze_candidate(self, release_id, candidate_sha, actor):
        _sha(candidate_sha)
        with self._tx() as db:
            release = self._release(db, release_id, True); self._approved(release)
            self._integrated(db, release_id)
            _require(release["qa_passed"] and release["qa_sha"] == candidate_sha == release["integration_sha"], "qa_required", "Freeze requires completed QA on the exact current integration revision.")
            _require(not db.execute("SELECT 1 FROM items WHERE release_id=? AND status<>'DONE'", (release_id,)).fetchone(), "unfinished_items", "Every story and bug must be done before freezing.")
            if release["candidate_sha"] == candidate_sha:
                return self._decoded(release)
            db.execute("UPDATE releases SET state='CANDIDATE_FROZEN',candidate_sha=?,release_approved_sha=NULL,release_approved_by=NULL WHERE id=?", (candidate_sha, release_id))
            self._event(db, release_id, "candidate_frozen", actor, {"candidate_sha": candidate_sha})
            return self._decoded(self._release(db, release_id))

    def approve_release(self, release_id, candidate_sha, actor):
        self._founder(actor); _sha(candidate_sha)
        with self._tx() as db:
            release = self._release(db, release_id, True)
            _require(release["candidate_sha"] == candidate_sha == release["qa_sha"] == release["integration_sha"] and release["qa_passed"], "stale_candidate", "Founder approval must match the frozen, QA-passed candidate exactly.")
            if release["release_approved_sha"] == candidate_sha:
                return self._decoded(release)
            db.execute("UPDATE releases SET state='RELEASE_APPROVED',release_approved_sha=?,release_approved_by=? WHERE id=?", (candidate_sha, actor, release_id))
            db.execute("INSERT INTO approvals(release_id,kind,target_hash,actor,created_at) VALUES(?,'release',?,?,?)", (release_id, candidate_sha, actor, self.clock()))
            self._event(db, release_id, "release_approved", actor, {"candidate_sha": candidate_sha})
            return self._decoded(self._release(db, release_id))

    def record_release(self, release_id, candidate_sha, idempotency_key, evidence, actor):
        _sha(candidate_sha); _identity(idempotency_key, "idempotency key"); raw = _evidence(evidence)
        payload = hashlib.sha256(_json({"release_id": release_id, "candidate_sha": candidate_sha, "evidence": evidence, "actor": actor}).encode()).hexdigest()
        with self._tx() as db:
            old = db.execute("SELECT * FROM release_records WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if old:
                _require(old["payload_hash"] == payload, "idempotency_conflict", "The idempotency key belongs to another payload.")
                return self._decoded(old)
            release = self._release(db, release_id, True)
            self._approved(release); self._integrated(db, release_id)
            _require(release["state"] == "RELEASE_APPROVED" and release["release_approved_sha"] == candidate_sha == release["candidate_sha"] == release["integration_sha"] == release["qa_sha"] and release["qa_passed"], "release_not_approved", "Exact candidate requires founder release approval and current QA.")
            _require(not db.execute("SELECT 1 FROM items WHERE release_id=? AND status<>'DONE'", (release_id,)).fetchone(), "unfinished_items", "Every item must be done.")
            db.execute("INSERT INTO release_records VALUES(?,?,?,?,?,?,?)", (idempotency_key, release_id, candidate_sha, payload, raw, actor, self.clock()))
            db.execute("UPDATE releases SET state='RELEASED',released_sha=? WHERE id=?", (candidate_sha, release_id))
            self._event(db, release_id, "release_recorded", actor, {"candidate_sha": candidate_sha, "idempotency_key": idempotency_key, "evidence": evidence})
            return self._decoded(db.execute("SELECT * FROM release_records WHERE idempotency_key=?", (idempotency_key,)).fetchone())

    def ready_items(self, release_id):
        with self._tx(False) as db:
            release = self._release(db, release_id)
            if not release["plan_hash"] or release["plan_hash"] != release["plan_approved_hash"] or release["state"] == "RELEASED":
                return []
            items = [self._decoded(r) for r in db.execute("SELECT * FROM items WHERE release_id=? ORDER BY kind,id", (release_id,))]
            status = {i["id"]: i["status"] for i in items if i["kind"] == "story"}
            live = [json.loads(r["scope"])["allowed_paths"] for r in db.execute("SELECT scope FROM items WHERE lease_until>?", (self.clock(),))]
            return [i for i in items if (i["status"] == "OPEN" or (i["status"] == "IN_PROGRESS" and (i["lease_until"] or 0) <= self.clock())) and i["attempts"] < i["max_attempts"] and all(status.get(d) in ("INTEGRATED", "DONE") for d in i["depends_on"]) and not any(_overlap(i["scope"]["allowed_paths"], paths) for paths in live)]

    def snapshot(self, release_id=None):
        with self._tx(False) as db:
            if release_id is not None:
                self._release(db, release_id)
            suffix, args = (" WHERE id=?", (release_id,)) if release_id else ("", ())
            releases = [self._decoded(r) for r in db.execute("SELECT * FROM releases" + suffix + " ORDER BY id", args)]
            suffix = " WHERE release_id=?" if release_id else ""
            items = [self._decoded(r) for r in db.execute("SELECT * FROM items" + suffix + " ORDER BY release_id,kind,id", args)]
            records = [self._decoded(r) for r in db.execute("SELECT * FROM release_records" + suffix + " ORDER BY release_id", args)]
        return {"releases": releases, "items": items, "release_records": records, "ready_items": [i for r in releases for i in self.ready_items(r["id"])]}

    status = snapshot

    def export_database(self):
        """Return a consistent SQLite byte snapshot for a trusted HMAC/CAS adapter.

        Never copy a live WAL-mode database by reading its main file alone. This
        method includes committed WAL contents through SQLite's backup API.
        HTTP publication, signature validation and remote compare-and-swap belong
        to the authenticated adapter, not this provider-independent ledger.
        """
        with self._connection() as source:
            with tempfile.TemporaryDirectory(prefix="sdlc-export-") as directory:
                path = Path(directory) / "snapshot.sqlite3"
                target = sqlite3.connect(path)
                try:
                    source.backup(target)
                    # A single portable file must not depend on WAL sidecars.
                    target.execute("PRAGMA journal_mode=DELETE")
                    target.commit()
                finally:
                    target.close()
                return path.read_bytes()

    def events(self, release_id=None):
        with self._tx(False) as db:
            return [self._decoded(r) for r in db.execute("SELECT * FROM events" + (" WHERE release_id=?" if release_id else "") + " ORDER BY seq", (release_id,) if release_id else ())]

    def verify_audit(self):
        previous = "0"*64
        for event in self.events():
            expected = hashlib.sha256(_json({k: event[k] for k in ("release_id", "type", "actor", "payload", "created_at", "previous_hash")}).encode()).hexdigest()
            _require(event["previous_hash"] == previous and event["event_hash"] == expected, "audit_mismatch", "Audit hash chain does not match.")
            previous = event["event_hash"]
        return {"valid": True, "head_hash": previous}


COMMANDS = {name: name for name in ("create_release", "upsert_story", "submit_plan", "approve_plan", "claim", "heartbeat", "associate_pr", "record_review", "record_ci", "integrate", "start_qa", "create_bug", "reopen_bug", "complete_qa", "freeze_candidate", "approve_release", "record_release", "snapshot", "status", "ready_items", "events", "verify_audit")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--founders", default="", help="Trusted operator configuration; never copied from event payloads")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--payload", help="JSON object; omitted means read stdin")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.payload if args.payload is not None else (sys.stdin.read() or "{}"))
        _require(isinstance(payload, dict), "invalid_payload", "Payload must be a JSON object.")
        control = Control(args.db, founder_ids=[x for x in args.founders.split(",") if x])
        try:
            result = getattr(control, COMMANDS[args.command])(**payload)
        except TypeError:
            raise ControlError("invalid_payload", "Arguments do not match the command contract.") from None
        print(_json({"ok": True, "result": result}))
        return 0
    except (ControlError, json.JSONDecodeError) as error:
        value = error.as_dict() if isinstance(error, ControlError) else {"code": "invalid_json", "message": "Payload is not valid JSON.", "details": {}}
        print(_json({"ok": False, "error": value}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
