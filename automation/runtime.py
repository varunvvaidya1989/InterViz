"""Trusted workspace/plan boundaries; model-mutated Git metadata is never executed."""
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from .providers import check_changed_paths, safe_path

SKIP = {".git", ".agent-output", ".sdlc", ".tools", "node_modules", ".venv", "__pycache__", ".next"}


def digest(value):
    data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def plan_document(path, policy, root):
    path = Path(path).resolve();root = Path(root).resolve()
    if not path.is_relative_to(root) or path.suffix != ".json": raise ValueError("Plan must be a local JSON manifest.")
    plan = json.loads(path.read_text(encoding="utf-8"))
    required = policy["gates"]["plan_approval"]["required_sections"]
    if any(not plan.get(section) for section in required): raise ValueError("Plan must contain stories, UI/UX, architecture, operations, acceptance tests and delivery tasks.")
    if not isinstance(plan.get("release_id"), str) or not isinstance(plan["user_stories"], list) or not plan["user_stories"]:
        raise ValueError("Plan needs a release ID and nonempty user stories.")
    ids = []
    for story in plan["user_stories"]:
        if not all(story.get(k) for k in ("id", "title", "allowed_paths", "acceptance")): raise ValueError("Every story needs ID/title/paths/acceptance.")
        if story.get("role", "coding") not in policy["roles"]: raise ValueError("Unsupported story role.")
        for p in story["allowed_paths"]: safe_path(p)
        ids.append(story["id"])
    if len(ids) != len(set(ids)): raise ValueError("Duplicate story ID.")
    by_id = {s["id"]: s for s in plan["user_stories"]};visiting=set();done=set()
    def visit(key):
        if key in visiting: raise ValueError("Story dependency cycle.")
        if key in done: return
        visiting.add(key)
        for dep in by_id[key].get("depends_on", []):
            if dep not in by_id: raise ValueError("Unknown story dependency.")
            visit(dep)
        visiting.remove(key);done.add(key)
    for key in ids: visit(key)
    return plan, digest({"plan": plan, "specification_sha256": digest((root / "planning/Systems Labs Product Specification.md").read_bytes()), "policy_sha256": digest(policy)})


def scan_files(workspace):
    root=Path(workspace).resolve();result={};total=0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs):
            candidate=Path(directory)/name
            if candidate.is_symlink(): raise ValueError("Worker symlinks are not publishable.")
        dirs[:]=[d for d in dirs if d not in SKIP]
        for name in files:
            path=Path(directory)/name
            if path.is_symlink(): raise ValueError("Worker symlinks are not publishable.")
            if path.stat().st_size>2_000_000: raise ValueError("Task file exceeds the 2MB publication limit.")
            data=path.read_bytes();total+=len(data)
            if total>30_000_000: raise ValueError("Task workspace exceeds the bounded scan limit.")
            result[path.relative_to(root).as_posix()]=digest(data)
    return result


def changes(before, after): return sorted(p for p in before.keys() | after.keys() if before.get(p)!=after.get(p))


def validate_assignment(paths, policy, infrastructure=False):
    cfg=policy["assignment_paths"]
    allowed=cfg["allowed_roots"]+cfg["allowed_root_files"]
    if infrastructure:
        if not policy["authority"]["infrastructure_implementation_authorized"]: raise ValueError("Infrastructure work is not authorised.")
        allowed+=cfg.get("infrastructure_roots",[])+cfg.get("infrastructure_root_files",[])
    for path in paths: check_changed_paths([path],allowed)


def protected_changes(paths, policy):
    return [p for p in paths if any(fnmatch.fnmatchcase(p, pattern) for pattern in policy["protected_paths"]["patterns"])]


def git(args, cwd, token=None, check=True):
    # Run only in trusted clones. Never call this on a model-modified .git directory.
    env={k:os.environ[k] for k in ("PATH","SYSTEMROOT","WINDIR","TEMP","TMP") if k in os.environ}
    env.update({"GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_NOSYSTEM":"1","GIT_CONFIG_GLOBAL":os.devnull,"GIT_CONFIG_COUNT":"0"})
    if token:
        import base64
        env.update({"GIT_CONFIG_COUNT":"1","GIT_CONFIG_KEY_0":"http.https://github.com/.extraheader","GIT_CONFIG_VALUE_0":"AUTHORIZATION: basic "+base64.b64encode(("x-access-token:"+token).encode()).decode()})
    result=subprocess.run(["git","-c","core.hooksPath="+os.devnull,"-c","core.fsmonitor=false",*args],cwd=cwd,env=env,text=True,encoding="utf-8",capture_output=True,timeout=90,check=False)
    if check and result.returncode: raise RuntimeError("Git operation failed; credentials and raw subprocess diagnostics are withheld.")
    return result.stdout.strip()


def publish_copy(workspace, clean_clone, paths):
    """Copy approved bytes; never reuse the worker's Git config/hooks/filters."""
    source=Path(workspace).resolve();target=Path(clean_clone).resolve()
    for name in paths:
        name=safe_path(name);src=source/name;dst=target/name
        if not dst.resolve().is_relative_to(target): raise ValueError("Publication path escapes clean clone.")
        if src.exists():
            if src.is_symlink() or not src.resolve().is_relative_to(source): raise ValueError("Unsafe publication source.")
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        elif dst.is_file(): dst.unlink()
