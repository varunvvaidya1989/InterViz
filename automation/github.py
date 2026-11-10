"""Small GitHub API boundary and signed, compare-and-swap controller snapshots."""
import base64
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class GitHubError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def local_git_credential():
    """Read an existing Git credential without displaying or persisting it.

    This never launches interactive authentication or changes credential settings.
    Only explicit local bootstrap uses it; CI uses its short-lived job token.
    """
    import subprocess
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    result = subprocess.run(["git", "-c", "credential.interactive=false", "credential", "fill"], input="protocol=https\nhost=github.com\n\n", text=True, capture_output=True, timeout=20, env=env, check=False)
    if result.returncode:
        return None
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return fields.get("password")


def repository_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise ValueError("Configure repository as owner/name.")
    return value


class GitHub:
    def __init__(self, repository, token=None, transport=None):
        self.repository = repository_name(repository)
        self.token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        self.transport = transport or urllib.request.urlopen
        if not self.token:
            raise GitHubError("GitHub access is not configured; provide GH_TOKEN to the trusted controller.")

    def request(self, method, path, body=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("GitHub API path must be relative.")
        request = urllib.request.Request("https://api.github.com" + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "SystemsLabs-SDLC", "Content-Type": "application/json"})
        try:
            with self.transport(request, timeout=45) as response:
                data = response.read()
                return json.loads(data) if data else {}
        except urllib.error.HTTPError as error:
            raise GitHubError(f"GitHub {method} request failed (HTTP {error.code}); no secret or upstream body is logged.", error.code) from None
        except (urllib.error.URLError, TimeoutError):
            raise GitHubError("GitHub could not be reached.") from None

    @property
    def root(self):
        return "/repos/" + self.repository

    def info(self): return self.request("GET", self.root)
    def pr(self, number): return self.request("GET", f"{self.root}/pulls/{int(number)}")
    def issue(self, number): return self.request("GET", f"{self.root}/issues/{int(number)}")
    def comment(self, number, body): return self.request("POST", f"{self.root}/issues/{int(number)}/comments", {"body": body})
    def create_issue(self, title, body, labels=None): return self.request("POST", self.root + "/issues", {"title": title, "body": body, "labels": labels or []})
    def pages(self,path,key=None):
        rows=[]
        for page in range(1,21):
            result=self.request("GET",path+("&" if "?" in path else "?")+"per_page=100&page="+str(page))
            batch=result[key] if key else result
            rows.extend(batch)
            if len(batch)<100:return rows
        raise GitHubError("Paginated result exceeds controller bound; refusing incomplete evidence.")
    def dispatch(self, workflow, inputs):
        info = self.info()
        return self.request("POST", f"{self.root}/actions/workflows/{urllib.parse.quote(workflow, safe='')}/dispatches", {"ref": info["default_branch"], "inputs": inputs})

    def ensure_branch(self, branch):
        encoded = urllib.parse.quote(branch, safe="")
        try:
            return self.request("GET", self.root + "/git/ref/heads/" + encoded)
        except GitHubError as error:
            if error.status != 404: raise
        info = self.info()
        base = self.request("GET", self.root + "/git/ref/heads/" + urllib.parse.quote(info["default_branch"], safe=""))
        return self.request("POST", self.root + "/git/refs", {"ref": "refs/heads/" + branch, "sha": base["object"]["sha"]})

    def file(self, path, ref):
        return self.request("GET", self.root + "/contents/" + urllib.parse.quote(path, safe="/") + "?ref=" + urllib.parse.quote(ref, safe=""))


def sign_snapshot(data, key):
    if not key or len(key) < 32:
        raise ValueError("SDLC_STATE_SIGNING_KEY must contain at least 32 characters.")
    digest = hashlib.sha256(data).hexdigest()
    signature = hmac.new(key.encode(), data, hashlib.sha256).hexdigest()
    return {"version": 1, "sha256": digest, "signature": signature, "database": base64.b64encode(data).decode()}


def verify_snapshot(envelope, key):
    if envelope.get("version") != 1:
        raise ValueError("Unsupported controller snapshot version.")
    data = base64.b64decode(envelope["database"], validate=True)
    expected = sign_snapshot(data, key)
    if not hmac.compare_digest(envelope.get("signature", ""), expected["signature"]) or envelope.get("sha256") != expected["sha256"]:
        raise ValueError("Controller state signature verification failed.")
    if data and not data.startswith(b"SQLite format 3\x00"):
        raise ValueError("Controller snapshot is not a SQLite database.")
    return data


class SnapshotStore:
    def __init__(self, github, db_path, key, branch="sdlc-state"):
        if not key or len(key)<32:raise ValueError("A controller signing key of at least 32 characters is required before any remote mutation.")
        self.github, self.db, self.key, self.branch = github, Path(db_path), key, branch
        self.manifest = self.db.with_suffix(".remote.json")
        self.path = "controller/state.json"

    def restore(self):
        self.db.parent.mkdir(parents=True, exist_ok=True)
        try:
            item = self.github.file(self.path, self.branch)
        except GitHubError as error:
            if error.status != 404: raise
            # Initialisation must be explicit; never silently discard a signed local ledger.
            if self.db.exists():
                raise GitHubError("Remote controller state is absent but local state exists; use an explicit bootstrap rather than overwrite it.")
            self.manifest.write_text(json.dumps({"sha": None, "initial": True}), encoding="utf-8")
            return {"restored": False, "initial": True}
        envelope = json.loads(base64.b64decode(item["content"]).decode())
        data = verify_snapshot(envelope, self.key)
        if not data:
            raise ValueError("Empty signed state is invalid.")
        temp = self.db.with_suffix(".restore.tmp")
        temp.write_bytes(data)
        temp.replace(self.db)
        self.manifest.write_text(json.dumps({"sha": item["sha"], "initial": False}), encoding="utf-8")
        return {"restored": True, "sha": item["sha"]}

    def save(self):
        if not self.manifest.exists():
            raise GitHubError("Restore controller state before saving it.")
        if not self.db.exists():
            raise GitHubError("No controller database to save.")
        # SQLite backup gives a consistent image even if the database uses WAL.
        import sqlite3
        temp = self.db.with_suffix(".backup.tmp")
        source = sqlite3.connect(self.db)
        target = sqlite3.connect(temp)
        try: source.backup(target)
        finally: target.close(); source.close()
        try: envelope = sign_snapshot(temp.read_bytes(), self.key)
        finally: temp.unlink(missing_ok=True)
        prior = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.github.ensure_branch(self.branch)
        body = {"message": "chore(sdlc): checkpoint signed controller state", "content": base64.b64encode(json.dumps(envelope, sort_keys=True).encode()).decode(), "branch": self.branch}
        if prior["sha"]: body["sha"] = prior["sha"]
        result = self.github.request("PUT", self.github.root + "/contents/" + self.path, body)
        # GitHub rejects a stale blob SHA; caller must restore/reconcile, not retry blind.
        self.manifest.write_text(json.dumps({"sha": result["content"]["sha"], "initial": False}), encoding="utf-8")
        return {"saved": True, "sha": result["content"]["sha"]}
