"""Install a container-specific sandbox profile on an ephemeral Linux runner."""
import json
import os
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
options=json.loads(subprocess.check_output(["docker","info","--format","{{json .SecurityOptions}}"],text=True))
if any("apparmor" in option for option in options):
    subprocess.run(["sudo","apparmor_parser","--replace",str(root/"infra/apparmor-codex")],check=True)
    with open(os.environ["GITHUB_ENV"],"a",encoding="utf-8") as handle:
        handle.write("SDLC_APPARMOR_PROFILE=systemslabs-codex\n")
    print("Installed container-specific AppArmor policy; native Codex sandbox remains enabled.")
else:
    print("Host does not use AppArmor; Docker seccomp and native sandbox preflight still apply.")
