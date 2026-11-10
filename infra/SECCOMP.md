# Nested Codex sandbox

Based on the Docker/Moby default seccomp profile at https://raw.githubusercontent.com/moby/profiles/4b8214fc4971e06172938a1f1554ccff6647ee80/seccomp/default.json.
The only additional allowed syscalls are clone, clone3, unshare, setns, mount, umount2 and pivot_root, needed to construct the inner bubblewrap sandbox. Docker capabilities remain dropped and no-new-privileges stays enabled. The Codex read-only/workspace-write sandbox remains enabled; unsupported hosts fail closed. No privileged mode, host namespace, Docker socket or host credentials are supplied.

Run a no-key compatibility check:

```powershell
docker run --rm --cap-drop=ALL --security-opt=no-new-privileges --security-opt=seccomp=infra/seccomp-codex.json systemslabs-agent:local codex sandbox -- /usr/bin/true
```

AppArmor hosts additionally load `infra/apparmor-codex` through `infra/prepare_runner.py`. This is the pinned Moby container profile with namespace construction/mount permissions for bubblewrap, retaining its `/proc`, `/sys`, networking, signal and tracing restrictions. It applies only to these worker containers; no host-wide security settings are disabled. Workers remain non-root with all Docker capabilities dropped. Hosted tasks fail before a model call if the inner sandbox cannot start.
