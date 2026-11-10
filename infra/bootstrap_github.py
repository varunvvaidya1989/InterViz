"""Bootstrap the explicitly selected GitHub repository without exposing credentials."""
import argparse
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from automation.github import GitHub,local_git_credential


def gh_binary(client):
    import shutil
    found=shutil.which("gh")
    if found:return Path(found)
    target=ROOT/".tools/gh/gh.exe"
    if target.exists():return target
    release=client.request("GET","/repos/cli/cli/releases/latest")
    archive=next(a for a in release["assets"] if a["name"].endswith("windows_amd64.zip"))
    checks=next(a for a in release["assets"] if a["name"].endswith("checksums.txt"))
    with urllib.request.urlopen(checks["browser_download_url"],timeout=60) as r:hashes=r.read().decode()
    expected=next(line.split()[0] for line in hashes.splitlines() if line.endswith(archive["name"]))
    with urllib.request.urlopen(archive["browser_download_url"],timeout=120) as r:data=r.read()
    if hashlib.sha256(data).hexdigest()!=expected:raise RuntimeError("GitHub CLI download checksum failed.")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        member=next(n for n in z.namelist() if n.endswith("bin/gh.exe"))
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(member))
    print("Installed checksum-verified GitHub CLI",release["tag_name"],"under ignored .tools/gh.")
    return target


def configure(client,token,gh):
    me=client.request("GET","/user");repo=client.info()
    if not repo.get("permissions",{}).get("admin"):raise RuntimeError("Repository administration permission is required for workflow configuration.")
    env={**os.environ,"GH_TOKEN":token,"GH_REPO":client.repository}
    names={s["name"] for s in client.request("GET",client.root+"/actions/secrets")["secrets"]}
    if "SDLC_STATE_SIGNING_KEY" not in names:
        key=secrets.token_urlsafe(48)
        result=subprocess.run([str(gh),"secret","set","SDLC_STATE_SIGNING_KEY","--repo",client.repository],input=key,text=True,capture_output=True,env=env,timeout=45,check=False)
        if result.returncode:raise RuntimeError("Could not create signing secret; raw CLI diagnostics withheld.")
        print("Configured signed-controller-state secret; value was not saved locally.")
    values={"SDLC_ENABLED":"true","SDLC_TRUSTED_ACTORS":json.dumps([me["login"]]),"SDLC_FOUNDER_LOGIN":me["login"]}
    for name,value in values.items():
        try:client.request("PATCH",client.root+"/actions/variables/"+name,{"name":name,"value":value})
        except Exception as error:
            if getattr(error,"status",None)!=404:raise
            client.request("POST",client.root+"/actions/variables",{"name":name,"value":value})
    client.request("PUT",client.root+"/environments/founder-release",{})
    print(json.dumps({"repository":repo["full_name"],"founder":me["login"],"controller_events_enabled":True,"worker_authority":"automation/policy.json and founder-approved release plans","openai_secret_present":"OPENAI_API_KEY" in names,"secret_values_disclosed":False},indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--repository",default="varunvvaidya1989/InterViz");p.add_argument("--download-only",action="store_true");p.add_argument("--configure",action="store_true");args=p.parse_args()
    token=os.environ.get("GH_TOKEN") or local_git_credential()
    if not token:raise RuntimeError("Authenticate GitHub locally first; no credential is requested in chat.")
    client=GitHub(args.repository,token=token);gh=gh_binary(client)
    if args.configure:configure(client,token,gh)
    elif not args.download_only:print("Use --configure after local validation and the initial repository push.")


if __name__=="__main__":main()
