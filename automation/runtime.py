"""Trusted workspace/plan boundaries; model-mutated Git metadata is never executed."""
import fnmatch
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .providers import check_changed_paths, safe_path

SKIP = {".git", ".agent-output", ".sdlc", ".tools", "node_modules", ".venv", "__pycache__", ".next"}
MAX_SOURCE_BYTES=2_000_000
MAX_SOURCE_FILES=100


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
    if check and result.returncode:
        # Only fixed labels cross this boundary: never echo arguments or stderr.
        operations={'clone','fetch','checkout','add','commit','push','rev-parse','merge-base','check-ref-format'}
        operation=next((arg for arg in args if arg in operations),'other')
        diagnostic=result.stderr.lower()
        reason='operation-failed'
        if 'refusing to allow' in diagnostic and ('workflow' in diagnostic):reason='workflow-write-permission-required'
        elif 'authentication failed' in diagnostic or 'could not read username' in diagnostic:reason='authentication-failed'
        elif 'non-fast-forward' in diagnostic or 'fetch first' in diagnostic:reason='remote-head-changed'
        elif 'could not resolve host' in diagnostic or 'failed to connect' in diagnostic:reason='transport-unavailable'
        raise RuntimeError('Git '+operation+' failed ('+reason+'); credentials and raw diagnostics are withheld.')
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


def credential_free(data,source=None):
    """Fail closed instead of putting known credentials into retained source."""
    source=os.environ if source is None else source
    for name,value in source.items():
        if value and len(str(value))>=4 and re.search(r'TOKEN|SECRET|PASSWORD|CREDENTIAL|API_KEY|SIGNING_KEY',name,re.I):
            raw=str(value).encode()
            if raw in data or base64.b64encode(raw) in data:
                raise ValueError('Source retention rejected credential material; raw bytes are withheld.')
    if re.search(rb'(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|github_pat_[A-Za-z0-9_]{12,})',data):
        raise ValueError('Source retention rejected credential material; raw bytes are withheld.')


def source_bundle(workspace,before,after,changed,allowed,source=None):
    root=Path(workspace).resolve();files={};total=0
    if len(changed)>MAX_SOURCE_FILES:raise ValueError('Source bundle exceeds the file limit.')
    if changed!=changes(before,after):raise ValueError('Changed paths do not match the handoff maps.')
    check_changed_paths(changed,allowed)
    for name in changed:
        if safe_path(name)!=name:raise ValueError('Source bundle paths must be canonical.')
        if name not in after:files[name]=None;continue
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Unsafe source retention path.')
        with path.open('rb') as stream:data=stream.read(MAX_SOURCE_BYTES-total+1)
        total+=len(data)
        if total>MAX_SOURCE_BYTES:raise ValueError('Source bundle exceeds the byte limit.')
        if digest(data)!=after[name]:raise ValueError('Source bytes changed after the handoff scan.')
        credential_free(data,source)
        files[name]=base64.b64encode(data).decode('ascii')
    bundle={'version':1,'files':files}
    validate_source_bundle(bundle,before,after,changed,allowed,source)
    return bundle


def validate_source_bundle(bundle,before,after,changed,allowed,source=None):
    if (not isinstance(bundle,dict) or set(bundle)!={'version','files'} or bundle['version']!=1
            or not isinstance(bundle['files'],dict) or len(bundle['files'])>MAX_SOURCE_FILES
            or sorted(bundle['files'])!=changed or changed!=changes(before,after)):
        raise ValueError('Source bundle identity or changed paths are invalid.')
    check_changed_paths(changed,allowed)
    decoded={};total=0
    for name,encoded in bundle['files'].items():
        if safe_path(name)!=name:raise ValueError('Source bundle paths must be canonical.')
        if encoded is None:
            if name in after or name not in before:raise ValueError('Invalid retained deletion.')
            decoded[name]=None;continue
        if not isinstance(encoded,str) or len(encoded)>((MAX_SOURCE_BYTES+2)//3)*4:
            raise ValueError('Source bundle exceeds the byte limit.')
        try:data=base64.b64decode(encoded,validate=True)
        except (ValueError,UnicodeError):raise ValueError('Source bundle has invalid encoded bytes.') from None
        total+=len(data)
        if total>MAX_SOURCE_BYTES:raise ValueError('Source bundle exceeds the byte limit.')
        if name not in after or digest(data)!=after[name]:raise ValueError('Source bundle hash does not match the handoff.')
        credential_free(data,source);decoded[name]=data
    return decoded


def publish_source_bundle(bundle,clean,before,after,changed,allowed,source=None):
    decoded=validate_source_bundle(bundle,before,after,changed,allowed,source)
    if scan_files(clean)!=before:raise ValueError('Clean publisher base bytes do not match the worker baseline.')
    root=Path(clean).resolve()
    for name,data in decoded.items():
        path=root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Unsafe publication path.')
        if data is None:
            if path.is_file():path.unlink()
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    if scan_files(clean)!=after:raise ValueError('Published bytes do not match the exact retained handoff.')


def publisher_checkout(root,clean,revision,repository):
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',revision or ''):
        raise ValueError('Publisher needs an exact base commit.')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):raise ValueError('Invalid publisher repository.')
    git(['clone','--no-hardlinks',str(root),str(clean)],root)
    if not git(['rev-parse','--verify',revision+'^{commit}'],clean,check=False):
        git(['fetch','https://github.com/'+repository+'.git',revision],clean)
    if git(['rev-parse','--verify',revision+'^{commit}'],clean)!=revision:
        raise ValueError('Publisher base object does not match the handoff.')
    git(['checkout','--detach',revision],clean)
    if git(['rev-parse','HEAD'],clean)!=revision:raise ValueError('Publisher checkout does not match the exact handoff base.')
