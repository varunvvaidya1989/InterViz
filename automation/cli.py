"""Trusted SDLC controller. No model response can approve, merge or release itself."""
import argparse
import fnmatch
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .control import Control, ControlError
from .github import GitHub, GitHubError, SnapshotStore
from .providers import DockerAgent, build_prompt, check_changed_paths
from .runtime import changes, digest, git, plan_document, protected_changes, publish_copy, scan_files, validate_assignment
from .approvals import validate_intent

ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/".sdlc/state.sqlite3"
OUT=ROOT/".sdlc/output"


def policy(): return json.loads((ROOT/"automation/policy.json").read_text(encoding="utf-8"))
def output(name,value):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/name).write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8");return value
def ledger(p): return Control(DB,founder_ids=p["founders"]["usernames"],max_attempts=p["limits"]["max_attempts"])
def github(p): return GitHub(p["repository"]["full_name"] or os.environ.get("GITHUB_REPOSITORY"))
def kv(key,value=None,write=False):
    DB.parent.mkdir(parents=True,exist_ok=True);db=sqlite3.connect(DB)
    try:
        db.execute("CREATE TABLE IF NOT EXISTS runtime_kv(key TEXT PRIMARY KEY,value TEXT NOT NULL)")
        if write: db.execute("INSERT INTO runtime_kv VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,json.dumps(value)));db.commit();return value
        row=db.execute("SELECT value FROM runtime_kv WHERE key=?",(key,)).fetchone();db.commit();return json.loads(row[0]) if row else None
    finally: db.close()


def principal(p,client=None):
    if os.environ.get("GITHUB_ACTIONS")!="true": raise ValueError("Remote authority requires a verified GitHub Actions run; use demo for local fixture execution.")
    client=client or github(p);run_id=os.environ.get("GITHUB_RUN_ID","")
    if not run_id.isdigit(): raise ValueError("Missing authenticated workflow run identity.")
    run=client.request("GET",client.root+"/actions/runs/"+run_id)
    actor=run.get("actor",{}).get("login")
    if actor!=os.environ.get("GITHUB_ACTOR") or run.get("repository",{}).get("full_name")!=client.repository: raise ValueError("Workflow identity does not match authenticated GitHub facts.")
    return actor


def require_live(p):
    if p["execution_mode"]!="live" or not p["providers"]["live_execution_enabled"]: raise ValueError("Live agents are disabled; configure policy/provider and budgets first.")
    if not p["founders"]["usernames"] or not p["repository"]["full_name"]: raise ValueError("Repository/founder configuration is required.")
    limits=p["limits"]
    if any(not isinstance(limits.get(k),(int,float)) or limits[k]<=0 for k in ("max_task_minutes","max_cost")): raise ValueError("Set positive task time and cost limits.")
    if p["providers"]["selected"]!="codex": raise ValueError("This repository is configured for the founder-selected Codex provider.")


def doctor(p):
    docker_ready=False
    if shutil.which("docker"):
        r=subprocess.run(["docker","info","--format","{{.ServerVersion}}"],capture_output=True,text=True,timeout=20,check=False);docker_ready=r.returncode==0
    missing=[]
    if not p["repository"]["connected"]:missing.append("GitHub repository bootstrap")
    if not p["founders"]["usernames"]:missing.append("founder usernames")
    if not docker_ready:missing.append("Docker engine")
    if not os.environ.get("OPENAI_API_KEY"):missing.append("OpenAI worker API key (repository secret may be configured remotely)")
    if p["execution_mode"]!="live":missing.append("explicit live execution policy")
    if not p["checks"]["application_configured"]:missing.append("SaaS application checks/staging (not implemented yet)")
    return {"docker_engine":docker_ready,"git_repository":(ROOT/".git").exists(),"execution_mode":p["execution_mode"],"repository":p["repository"]["full_name"],"provider":p["providers"]["selected"],"missing":missing,"ready_for_live_agents":not missing,"production_release_enabled":p["authority"]["production_release_enabled"]}


def probe(p):
    require_live(p)
    home=ROOT/".sdlc/workspaces"/("probe-"+uuid.uuid4().hex);home.mkdir(parents=True)
    git(["init"],home)
    report=DockerAgent().run(home,"qa","codex","Infrastructure connectivity check only. Do not use tools or change any file. Return the structured report with verdict PASS, summary 'Codex connectivity verified', empty findings, evidence ['live provider response'], limitations ['This verifies connectivity only; no application or release is approved.'].",timeout=120)
    if report["verdict"]!="PASS":raise ValueError("Provider connectivity check did not pass.")
    return output("provider-probe.json",{"status":"PASS","provider":"codex","live":True,"scope":"connectivity only","report":report})


def validate(p,scope,revision=None):
    if scope=="infrastructure":
        b=json.loads((ROOT/"agents/backlog.json").read_text(encoding="utf-8"));r=json.loads((ROOT/"agents/requirements.json").read_text(encoding="utf-8"));ids={x["id"] for x in r["requirements"]};tasks={x["id"]:x for x in b["tasks"]}
        if not all(set(t["requirements"])<=ids and set(t["depends_on"])<=tasks.keys() for t in tasks.values()):raise ValueError("Invalid task/requirement dependency references.")
        visiting=set();done=set()
        def visit(key):
            if key in visiting:raise ValueError("Task dependency cycle.")
            if key in done:return
            visiting.add(key)
            for dep in tasks[key]["depends_on"]:visit(dep)
            visiting.remove(key);done.add(key)
        for key in tasks:visit(key)
        if set(p["roles"])!={"lead","coding","ui-ux","devops","review","qa"}:raise ValueError("Invalid role policy.")
        if p["limits"]["max_attempts"]>2 or p["limits"]["max_review_rounds"]>2:raise ValueError("Unbounded rework policy.")
        if not p["gates"]["plan_approval"]["founder_only"] or not p["gates"]["release_approval"]["founder_only"]:raise ValueError("Founder gate disabled.")
        return output("validation.json",{"scope":scope,"revision":revision,"status":"PASS","checks":["policy","task graph","requirement references"],"note":"Unit/E2E jobs run separately; this is not SaaS acceptance."})
    if scope not in {"application","staging"}:raise ValueError("Unsupported validation scope.")
    if revision and git(["rev-parse","HEAD"],ROOT)!=revision:raise ValueError("Validation checkout does not match the claimed candidate revision.")
    if not p["checks"]["application_configured"] or not p["checks"]["application"]:raise ValueError("Application checks are not configured; cannot report a false QA pass.")
    if scope=="staging" and not p["environment"]["staging"]["configured"]:raise ValueError("A real staging deployment must be configured before staging QA.")
    results=[]
    for check in p["checks"]["application"]:
        command=check["command"]
        if not isinstance(command,list) or not command or any(not isinstance(v,str) for v in command):raise ValueError("Checks must be explicit argument arrays.")
        run=subprocess.run(command,cwd=ROOT/check.get("cwd","."),capture_output=True,text=True,timeout=600,check=False)
        results.append({"id":check["id"],"passed":run.returncode==0})
    report={"scope":scope,"revision":revision,"status":"PASS" if all(r["passed"] for r in results) else "FAIL","checks":results};output("validation.json",report)
    if report["status"]!="PASS":raise ValueError("Configured application checks failed.")
    return report


def find_item(control,reference):
    parts=reference.split(":")
    if len(parts)!=3 or parts[1] not in {"story","bug"}:raise ValueError("Task ID must be RELEASE:story|bug:ITEM.")
    release_id,kind,item_id=parts
    item=next((i for i in control.snapshot(release_id)["items"] if i["id"]==item_id and i["kind"]==kind),None)
    if not item:raise ValueError("Task is absent from the founder-approved ledger.")
    return release_id,kind,item_id,item


def adopt_plan(p,control,path,actor):
    plan,plan_hash=plan_document(path,p,ROOT);release_id=plan["release_id"]
    existing={r["id"] for r in control.snapshot()["releases"]}
    if release_id not in existing:control.create_release(release_id,plan.get("title",release_id),actor,{"plan_path":str(Path(path).resolve().relative_to(ROOT))})
    for story in plan["user_stories"]:
        validate_assignment(story["allowed_paths"],p,infrastructure=story.get("kind")=="infrastructure")
        control.upsert_story(release_id,story["id"],story["title"],{"allowed_paths":story["allowed_paths"],"acceptance":story["acceptance"],"role":story.get("role","coding"),"kind":story.get("kind","application")},story.get("depends_on",[]),actor)
    result=control.submit_plan(release_id,plan_hash,actor);kv("plan:"+release_id,{"path":str(Path(path).resolve().relative_to(ROOT)),"hash":plan_hash},True);return result


def current_plan(p,release_id):
    manifest=kv("plan:"+release_id)
    if not manifest:raise ValueError("No reviewed release plan exists.")
    if "document" in manifest:
        actual=digest({"plan":manifest["document"],"specification_sha256":digest((ROOT/"planning/Systems Labs Product Specification.md").read_bytes()),"policy_sha256":digest(p)})
    else:_,actual=plan_document(ROOT/manifest["path"],p,ROOT)
    return manifest,actual


def revise_plan(control,release_id,feedback,actor):
    result=control.request_plan_revision(release_id,feedback,actor)
    kv("previous-plan:"+release_id,kv("plan:"+release_id),True)
    kv("plan:"+release_id,None,True)
    kv("plan-feedback:"+release_id,feedback,True)
    return result


def prepare_candidate(p,control,release_id,revision,actor):
    result=control.freeze_candidate(release_id,revision,actor)
    prior=kv('candidate:'+release_id)
    snapshot=control.snapshot(release_id)
    if (prior and prior.get('commit_sha')==revision and prior.get('policy_sha256')==digest(p)
            and prior.get('evidence_sha256')==digest(snapshot)):
        return result,prior
    candidate={'commit_sha':revision,'changelog':'\n'.join('- '+i['title'] for i in snapshot['items']),
               'evidence_sha256':digest(snapshot),'policy_sha256':digest(p)}
    kv('candidate:'+release_id,candidate,True)
    return result,candidate


def approve(p,args):
    """Only authenticated founder workflow execution consumes dashboard intent."""
    validate_intent({'kind':args.kind,'release_id':args.release_id,
                     'expected_hash':args.expected_hash,'revision':args.revision})
    client=github(p);actor=principal(p,client)
    if actor not in p['founders']['usernames']:
        raise ValueError('Only the configured founder may approve.')
    control=ledger(p);release_id=args.release_id
    if args.kind=='plan':
        manifest,actual=current_plan(p,release_id)
        if actual!=args.expected_hash or manifest.get('hash')!=actual:
            raise ValueError('The plan changed. Refresh and review it again.')
        expected_revision=manifest.get('revision') or git(['rev-parse','HEAD'],ROOT)
        if args.revision!=expected_revision:
            raise ValueError('The displayed plan revision is stale.')
        if manifest.get('pr_url'):
            pr=client.pr(int(manifest['pr_url'].rsplit('/',1)[1]))
            if pr['head']['sha']!=args.revision or pr['head']['repo']['full_name']!=client.repository:
                raise ValueError('The planning PR changed. Refresh and review it again.')
            if pr['state']=='closed' and not pr.get('merged'):
                raise ValueError('The planning PR was withdrawn.')
        result=control.approve_plan(release_id,actual,actor)
    else:
        manifest,actual=current_plan(p,release_id)
        current=control.snapshot(release_id)['releases'][0]
        if current.get('plan_approved_hash')!=actual:
            raise ValueError('The plan approval is missing or stale.')
        candidate=kv('candidate:'+release_id)
        if (not candidate or digest(candidate)!=args.expected_hash or candidate.get('commit_sha')!=args.revision
                or candidate.get('policy_sha256')!=digest(p)):
            raise ValueError('The release changed. Refresh and review it again.')
        result=control.approve_release(release_id,args.revision,actor)
        kv('release-manifest-approval:'+release_id,{'manifest_hash':args.expected_hash,'actor':actor},True)
    return output('founder-approval.json',{'kind':args.kind,'release_id':release_id,'actor':actor,
                                        'revision':args.revision,'approved_hash':args.expected_hash,'result':result})


def pr_files(client,pr,item,p):
    files=client.pages(client.root+f"/pulls/{pr['number']}/files")
    if len(files)!=pr.get("changed_files",len(files)):raise ValueError("Incomplete PR file evidence.")
    paths=[f["filename"] for f in files]
    # Renames must also authorise the removed old path.
    paths += [f["previous_filename"] for f in files if f.get("previous_filename")]
    check_changed_paths(paths,item["scope"]["allowed_paths"])
    return files,protected_changes(paths,p)


def record_ci_run(p,client,control,run):
    expected=client.request("GET",client.root+"/actions/workflows/infrastructure-ci.yml")
    if run.get("workflow_id")!=expected["id"] or run.get("status")!="completed":return
    # GitHub can complete a run while it awaits maintainer approval, before any
    # job executes. This is not executable CI evidence and may later be rerun.
    if run.get("conclusion")=="action_required":return
    prs=[]
    if run.get("event")=="pull_request":prs=run.get("pull_requests",[]);target=run["head_sha"]
    elif run.get("event")=="workflow_dispatch":
        match=re.fullmatch(r"SDLC CI workflow_dispatch pr=(\d+) sha=([a-f0-9]{40,64})",run.get("display_title",""))
        if not match:return
        prs=[{"number":int(match[1])}];target=match[2]
        if not kv("ci-queued:"+target):return
    else:return
    receipt="ci-run:"+str(run["id"])
    if kv(receipt):return
    for ref in prs:
        pr=client.pr(ref["number"])
        if pr["head"]["sha"]!=target or pr["head"]["repo"]["full_name"]!=client.repository:continue
        for item in control.snapshot()["items"]:
            if item.get("pr_url")!=pr["html_url"] or item.get("head_sha")!=target:continue
            _,protected=pr_files(client,pr,item,p)
            # A PR cannot redefine the CI that certifies itself.
            base=client.file(".github/workflows/infrastructure-ci.yml",client.info()["default_branch"])
            proposed=client.file(".github/workflows/infrastructure-ci.yml",target)
            if base["sha"]!=proposed["sha"]:raise ValueError("CI workflow changes need separate trusted acceptance.")
            passed=run.get("conclusion")=="success"
            control.record_ci(item["release_id"],item["id"],target,passed,{"run_id":run["id"],"url":run["html_url"],"workflow_id":expected["id"]},"github:ci",kind=item["kind"])
            client.request("POST",client.root+"/check-runs",{"name":"sdlc-infrastructure-ci","head_sha":target,"status":"completed","conclusion":"success" if passed else "failure","output":{"title":"Verified CI provenance","summary":run["html_url"]}})
    kv(receipt,{"processed":True},True)


def event(p,args):
    client=github(p);actor=principal(p,client);control=ledger(p);data=json.loads(Path(args.event_path).read_text(encoding="utf-8"));name=args.event_name
    if name=="workflow_run":
        run_id=data.get("workflow_run",{}).get("id");run=client.request("GET",client.root+f"/actions/runs/{int(run_id)}")
        record_ci_run(p,client,control,run)
        return {"processed":"verified CI"}
    if name=="pull_request_review" and actor in p["founders"]["usernames"]:
        review=data.get("review",{});pr=client.pr(data["pull_request"]["number"])
        if review.get("user",{}).get("login")!=actor or review.get("commit_id")!=pr["head"]["sha"]:raise ValueError("Review author/revision is stale.")
        verdict={"approved":"APPROVE","changes_requested":"REQUEST_CHANGES"}.get(review.get("state",""))
        if verdict and actor!=pr["user"]["login"]:
            for item in control.snapshot()["items"]:
                if item.get("pr_url")==pr["html_url"] and item.get("head_sha")==pr["head"]["sha"]:
                    who="github:"+actor
                    control.record_review(item["release_id"],item["id"],item["head_sha"],who,verdict,{"review_url":review["html_url"]},who,kind=item["kind"])
        return {"processed":"authenticated human review"}
    comment=data.get("comment",{});text=comment.get("body","")
    if name=="issue_comment" and text.startswith("/sdlc "):
        # Exact authenticated comment author, not a model-supplied actor.
        if comment.get("user",{}).get("login")!=actor:raise ValueError("Comment author mismatch.")
        receipt="comment:"+str(comment["id"])
        if kv(receipt):return {"processed":"duplicate ignored"}
        words=text.strip().split();command=words[1]
        if actor not in p["founders"]["usernames"]:raise ValueError("Only configured founders issue release-plan/release approval commands.")
        if command=="plan" and len(words)==3:result=adopt_plan(p,control,ROOT/words[2],actor)
        elif command=="revise-plan" and len(words)>=4:result=revise_plan(control,words[2]," ".join(words[3:]),actor)
        elif command=="approve-plan" and len(words)==4:
            manifest,actual=current_plan(p,words[2])
            if words[3]!=actual:raise ValueError("Approval does not match current plan/spec/policy hashes.")
            result=control.approve_plan(words[2],actual,actor)
        elif command=="approve-release" and len(words)==5:
            candidate=kv("candidate:"+words[2])
            if not candidate or words[4]!=digest(candidate) or candidate["commit_sha"]!=words[3]:raise ValueError("Candidate artifact/evidence hash does not match founder approval.")
            result=control.approve_release(words[2],words[3],actor);kv("release-manifest-approval:"+words[2],{"manifest_hash":words[4],"actor":actor},True)
        else:raise ValueError("Commands: /sdlc plan PATH; /sdlc revise-plan RELEASE FEEDBACK; /sdlc approve-plan RELEASE HASH; /sdlc approve-release RELEASE SHA MANIFEST_HASH")
        kv(receipt,{"processed":True,"actor":actor},True);return result
    if name=="issues" and "sdlc:plan" in [l["name"] for l in data.get("issue",{}).get("labels",[])]:
        issue=data["issue"];release_id="R-"+str(issue["number"])
        if release_id not in {r["id"] for r in control.snapshot()["releases"]}:control.create_release(release_id,issue["title"],actor,{"issue":issue["number"],"direction":issue.get("body","")[:12000]})
        return {"release_id":release_id,"state":"DRAFT","next":"lead planning"}
    return {"processed":"no authoritative transition"}


def worker(p,args):
    require_live(p);control=ledger(p)
    if not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}",args.revision or ""):raise ValueError("Worker needs an exact target revision.")
    role=args.role;key="queue:"+role+":"+args.task_id;queued=kv(key)
    if not queued or queued.get("revision")!=args.revision:raise ValueError("Worker was not queued by the authenticated controller for this exact revision.")
    planning=role=="lead" and args.task_id.endswith(":plan:release")
    if planning:
        release_id=args.task_id.split(":")[0];kind="plan";item_id="release"
        item={"scope":{"allowed_paths":["docs/releases/"+release_id],"acceptance":["Create plan.json with release_id/title, user_stories (each id/title/allowed_paths/acceptance/depends_on/role/kind), ui_ux, architecture, operations, acceptance_tests, delivery_tasks; each section must be comprehensive and implementable."]}}
        manifest=None;current_hash=None
    else:
        release_id,kind,item_id,item=find_item(control,args.task_id)
        manifest,current_hash=current_plan(p,release_id)
    release=control.snapshot(release_id)["releases"][0]
    if role=="review" and (item.get("head_sha")!=args.revision or item.get("status")!="SUBMITTED"):raise ValueError("Review target is no longer the submitted current head.")
    if role=="qa" and (release.get("qa_sha")!=args.revision or release.get("state")!="QA"):raise ValueError("QA target is no longer the active QA candidate.")
    if not planning and release.get("plan_approved_hash")!=current_hash:raise ValueError("Plan approval is missing or stale.")
    if not planning and role not in {"review","qa"} and not p["checks"]["application_configured"] and item["scope"].get("kind")!="infrastructure":raise ValueError("Configure SaaS application checks before dispatching application coding.")
    worker_id=f"{role}:{release_id}:{item_id}:{uuid.uuid4().hex[:12]}"
    count_key="worker-attempt:"+role+":"+args.task_id+":"+args.revision
    attempts=kv(count_key) or 0
    if attempts>=p["limits"]["max_attempts"]:raise ValueError("Worker attempt bound reached; lead intervention required.")
    kv(count_key,attempts+1,True)
    claim=None
    if not planning and role not in {"review","qa"}:claim=control.claim(release_id,item_id,worker_id,kind=kind,lease_seconds=min(3600,int(p["limits"]["max_task_minutes"]*60)+60))
    home=ROOT/".sdlc/workspaces"/uuid.uuid4().hex;home.parent.mkdir(parents=True,exist_ok=True)
    git(["clone","--no-hardlinks",str(ROOT),str(home)],ROOT)
    # Target is a Git object, never a shell fragment. Public repository fetch can
    # prepare a missing object without placing GitHub credentials in a worker.
    # The controller and prompt still come from trusted ROOT. Only the isolated,
    # credential-free agent workspace contains the exact submitted candidate.
    checkout_revision=args.revision
    if not git(["rev-parse","--verify",checkout_revision+"^{commit}"],home,check=False):
        git(["fetch","https://github.com/"+p["repository"]["full_name"]+".git",checkout_revision],home)
    git(["checkout","--detach",checkout_revision],home)
    if git(["rev-parse","HEAD"],home)!=args.revision:
        raise ValueError("Worker workspace does not match the exact target revision.")
    before=scan_files(home)
    feedback=[e["payload"] for e in control.events(release_id) if e["type"]=="review_recorded" and e["payload"].get("item_id")==item_id]
    assignment={"release_id":release_id,"item_id":item_id,"role":role,"scope":item["scope"],"target_revision":args.revision,"plan_hash":current_hash,"founder_approval":release.get("plan_approved_by"),"release_direction":release.get("metadata"),"approved_plan":manifest.get("document") if manifest else None,"review_feedback":feedback[-4:],"release_items":control.snapshot(release_id)["items"] if role=="qa" else None}
    if planning:assignment.update(previous_plan=kv("previous-plan:"+release_id),founder_feedback=kv("plan-feedback:"+release_id))
    diff=""
    if role=="review":
        # Diff was fetched/authenticated by the controller, not supplied by model.
        diff=queued.get("diff","")
    report=DockerAgent().run(home,role,p["providers"]["selected"],build_prompt(ROOT,role,assignment,diff),model=p["providers"].get("model"),timeout=int(p["limits"]["max_task_minutes"]*60),budget_usd=p["limits"]["max_cost"])
    if role not in {"review","qa"} and report["verdict"]!="SUBMITTED":raise ValueError("Worker reported blocked/unsuccessful work; lead rework is required before a PR.")
    after=scan_files(home);changed=changes(before,after)
    if role in {"review","qa"} and changed:raise ValueError("Read-only review/QA changed workspace files.")
    if role not in {"review","qa"}:check_changed_paths(changed,item["scope"]["allowed_paths"])
    if planning:
        plan,unused=plan_document(home/"docs/releases"/release_id/"plan.json",p,home)
        if plan["release_id"]!=release_id:raise ValueError("Plan release identity changed.")
        for story in plan["user_stories"]:validate_assignment(story["allowed_paths"],p,infrastructure=story.get("kind")=="infrastructure")
    return output("worker-result.json",{"role":role,"reference":args.task_id,"worker_id":worker_id,"revision":args.revision,"workspace":str(home),"baseline":before,"after":after,"changed_paths":changed,"report":report,"lease_id":claim.get("lease_id") if claim else None,"kind":kind,"plan_hash":current_hash})


def publish_result(p,client,control):
    file=OUT/"worker-result.json"
    if not file.exists():return None
    result=json.loads(file.read_text(encoding="utf-8"));marker="worker-result:"+digest(result)
    if kv(marker):return None
    role=result["role"];report=result["report"];planning=role=="lead" and result["kind"]=="plan"
    if planning:
        release_id=result["reference"].split(":")[0];kind="plan";item_id="release";item={"title":"Release plan","attempts":1,"scope":{"allowed_paths":["docs/releases/"+release_id]}}
    else:release_id,kind,item_id,item=find_item(control,result["reference"])
    if role=="review":
        verdict="APPROVE" if report["verdict"]=="APPROVE" and not any(f["severity"] in {"critical","high","normal"} for f in report["findings"]) else "REQUEST_CHANGES"
        control.record_review(release_id,item_id,result["revision"],result["worker_id"],verdict,{"report":report,"execution":os.environ.get("GITHUB_RUN_ID")},result["worker_id"],kind=kind)
        kv("reviewed:"+result["reference"]+":"+result["revision"],{"verdict":verdict},True)
        client.request("POST",client.root+"/check-runs",{"name":"sdlc-independent-review","head_sha":result["revision"],"status":"completed","conclusion":"success" if verdict=="APPROVE" else "failure","output":{"title":"Independent agent review","summary":report["summary"][:60000]}})
        number=int(item["pr_url"].rsplit("/",1)[1]);client.comment(number,"### Independent agent review\nVerdict: "+verdict+"\n\n"+report["summary"]+"\n\n"+"\n".join("- "+f["severity"]+": "+f["description"] for f in report["findings"]))
    elif role=="qa":
        if report["verdict"]=="PASS" and not report["findings"]:
            validation=json.loads((OUT/"validation.json").read_text(encoding="utf-8"))
            if validation.get("scope")!="staging" or validation.get("revision")!=result["revision"] or validation.get("status")!="PASS":raise ValueError("QA needs actual matching staging validation, not only a model verdict.")
            control.complete_qa(release_id,result["revision"],{"report":report,"validation":validation},result["worker_id"])
        else:
            for f in report["findings"]:
                bug_id="BUG-"+digest({"release":release_id,"finding":f})[:12]
                existing=next((x for x in control.snapshot(release_id)["items"] if x["id"]==bug_id),None)
                if not existing:control.create_bug(release_id,bug_id,f["description"],result["worker_id"],scope=item["scope"],story_id=item_id,severity=f["severity"])
                issue=client.create_issue("[Bug] "+f["description"][:180],f"Release: {release_id}\nStory: {item_id}\nBug: {bug_id}\n\n{f['reproduction']}\n\n<!-- sdlc:{bug_id} -->")
                kv("bug-issue:"+bug_id,issue["number"],True)
    else:
        changed=result["changed_paths"]
        if not changed:raise ValueError("Coding worker produced no publishable change; return it to the lead.")
        home=Path(result["workspace"]).resolve()
        if not home.is_relative_to((ROOT/".sdlc/workspaces").resolve()):raise ValueError("Worker workspace location is invalid.")
        if scan_files(home)!=result["after"]:raise ValueError("Worker bytes changed after its handoff.")
        check_changed_paths(changed,item["scope"]["allowed_paths"])
        clean=ROOT/".sdlc/publish"/uuid.uuid4().hex;clean.parent.mkdir(parents=True,exist_ok=True)
        git(["clone","--no-hardlinks",str(ROOT),str(clean)],ROOT);git(["checkout","--detach",result["revision"]],clean)
        branch="agent/"+re.sub(r"[^A-Za-z0-9._-]","-",release_id+"-"+item_id)+"-"+str(item["attempts"])
        if planning:branch+="-"+uuid.uuid4().hex[:8]
        git(["checkout","-b",branch],clean);publish_copy(home,clean,changed)
        git(["add","--",*changed],clean)
        git(["-c","user.name=Systems Labs Agent","-c","user.email=41898282+github-actions[bot]@users.noreply.github.com","commit","-m",f"feat({item_id}): {item['title'][:120]}"],clean)
        sha=git(["rev-parse","HEAD"],clean);git(["push","https://github.com/"+client.repository+".git","HEAD:refs/heads/"+branch],clean,token=client.token)
        info=client.info();pr=client.request("POST",client.root+"/pulls",{"title":f"[{release_id}/{item_id}] {item['title']}","head":branch,"base":info["default_branch"],"body":report["summary"]+f"\n\n<!-- sdlc:{release_id}:{kind}:{item_id} -->\nPlan: {result['plan_hash']}\nAuthor execution: {result['worker_id']}"})
        if planning:
            plan_path=home/"docs/releases"/release_id/"plan.json";plan,plan_hash=plan_document(plan_path,p,home)
            if plan["release_id"]!=release_id:raise ValueError("Lead plan changed the founder release ID.")
            for story in plan["user_stories"]:
                validate_assignment(story["allowed_paths"],p,infrastructure=story.get("kind")=="infrastructure")
                control.upsert_story(release_id,story["id"],story["title"],{"allowed_paths":story["allowed_paths"],"acceptance":story["acceptance"],"role":story.get("role","coding"),"kind":story.get("kind","application")},story.get("depends_on",[]),result["worker_id"])
            control.submit_plan(release_id,plan_hash,result["worker_id"]);kv("plan:"+release_id,{"document":plan,"hash":plan_hash,"pr_url":pr["html_url"],"revision":sha},True)
            client.comment(pr["number"],"Founder review: open the founder dashboard, review the plan and select Approve plan. No command comment is needed. Changes to stories, specification or policy require renewed approval.")
        else:
            control.associate_pr(release_id,item_id,sha,pr["html_url"],result["worker_id"],result["worker_id"],kind=kind,lease_id=result["lease_id"])
            if item.get("pr_url") and item["pr_url"]!=pr["html_url"]:
                old=int(item["pr_url"].rsplit("/",1)[1]);client.comment(old,"Superseded by bounded rework: "+pr["html_url"]);client.request("PATCH",client.root+f"/pulls/{old}",{"state":"closed"})
        kv("protected:"+pr["html_url"],protected_changes(changed,p),True)
    kv(marker,{"published":True},True);kv("queue:"+role+":"+result["reference"],None,True);return {"processed_worker":role,"reference":result["reference"]}


def reconcile(p,args):
    client=github(p);principal(p,client);control=ledger(p);processed=publish_result(p,client,control)
    existing={r["id"] for r in control.snapshot()["releases"]}
    for issue in client.pages(client.root+"/issues?state=open&labels=sdlc%3Aplan"):
        release_id="R-"+str(issue["number"])
        if "pull_request" in issue or issue.get("user",{}).get("login") not in p["founders"]["usernames"] or release_id in existing:continue
        control.create_release(release_id,issue["title"],issue["user"]["login"],{"issue":issue["number"],"direction":issue.get("body","")[:12000]})
        existing.add(release_id)
    # Scheduled rescanning means GitHub concurrency coalescing loses no approval.
    for comment in client.pages(client.root+"/issues/comments"):
        if comment.get("user",{}).get("login") not in p["founders"]["usernames"] or not comment.get("body","").startswith("/sdlc "):continue
        if kv("comment:"+str(comment["id"])):continue
        # Authenticated GitHub API supplies actor, and trusted scheduled controller
        # is permitted to replay that immutable fact without impersonating it.
        words=comment["body"].strip().split();actor=comment["user"]["login"]
        try:
            if words[1]=="plan" and len(words)==3:adopt_plan(p,control,ROOT/words[2],actor)
            elif words[1]=="revise-plan" and len(words)>=4:revise_plan(control,words[2]," ".join(words[3:]),actor)
            elif words[1]=="approve-plan" and len(words)==4:
                manifest,actual=current_plan(p,words[2])
                if actual!=words[3]:continue
                control.approve_plan(words[2],actual,actor)
            elif words[1]=="approve-release" and len(words)==5:
                candidate=kv("candidate:"+words[2])
                if not candidate or words[4]!=digest(candidate) or candidate["commit_sha"]!=words[3]:continue
                control.approve_release(words[2],words[3],actor);kv("release-manifest-approval:"+words[2],{"manifest_hash":words[4],"actor":actor},True)
            else:continue
            kv("comment:"+str(comment["id"]),{"processed":True,"actor":actor},True)
        except (ValueError,ControlError,TypeError):continue
    if p["execution_mode"]!="live" or not p["providers"]["live_execution_enabled"]:return {"mode":"dry-run","worker_result":processed,"queued":[],"note":"No paid model calls or merges are enabled."}
    require_live(p);scheduled=[]
    for run in client.pages(client.root+"/actions/workflows/infrastructure-ci.yml/runs",key="workflow_runs"):
        if run.get("status")=="completed":record_ci_run(p,client,control,run)
    for release in control.snapshot()["releases"]:
        if release["state"]=="RELEASED":continue
        if release["state"]=="DRAFT" and not kv("plan:"+release["id"]):
            reference=release["id"]+":plan:release";key="queue:lead:"+reference;queued=kv(key)
            if not queued or queued.get("time",0)<time.time()-1800:
                info=client.info();base=client.request("GET",client.root+"/git/ref/heads/"+info["default_branch"])["object"]["sha"]
                kv(key,{"revision":base,"time":time.time()},True);client.dispatch("agent-control.yml",{"action":"worker","role":"lead","task-id":reference,"revision":base});scheduled.append(key)
            continue
        for item in control.snapshot(release["id"])["items"]:
            issue_key="work-issue:"+release["id"]+":"+item["kind"]+":"+item["id"]
            if item["kind"]=="story" and not kv(issue_key):
                issue=client.create_issue("[Story] "+item["title"][:180],f"Release: {release['id']}\nItem: {item['id']}\n\nAcceptance:\n"+"\n".join("- "+a for a in item["scope"]["acceptance"])+"\n\nScope: "+", ".join(item["scope"]["allowed_paths"]),labels=["sdlc:story"])
                kv(issue_key,issue["number"],True)
            if item["status"]=="OPEN" and item["attempts"]>=item["max_attempts"]:
                marker="escalated:"+release["id"]+":"+item["id"]
                if not kv(marker):
                    issue=client.create_issue("[Lead review] "+item["title"],"Bounded developer/review attempts exhausted. Re-plan or split this work; do not waive failed acceptance.\n\nRelease: "+release["id"]+"\nItem: "+item["id"]);kv(marker,issue["number"],True)
            if item["status"]!="SUBMITTED":continue
            pr=client.pr(int(item["pr_url"].rsplit("/",1)[1]))
            files,protected=pr_files(client,pr,item,p)
            kv("protected:"+item["pr_url"],protected,True)
            if pr["head"]["sha"]!=item["head_sha"]:
                control.associate_pr(release["id"],item["id"],pr["head"]["sha"],pr["html_url"],pr["user"]["login"],"github:head-update",kind=item["kind"]);continue
            if pr.get("merged"):
                if pr.get("merged_by",{}).get("login") not in p["founders"]["usernames"]:raise ValueError("Out-of-controller merge requires founder reconciliation.")
                control.integrate(release["id"],item["id"],item["head_sha"],pr["merge_commit_sha"],"github:founder-merge",kind=item["kind"])
                continue
            key="queue:review:"+release["id"]+":"+item["kind"]+":"+item["id"]
            queued=kv(key)
            if not kv("reviewed:"+release["id"]+":"+item["kind"]+":"+item["id"]+":"+item["head_sha"]) and (not queued or queued.get("revision")!=item["head_sha"] or queued.get("time",0)<time.time()-1800):
                if any("patch" not in f for f in files):raise ValueError("Review diff is incomplete/binary/oversized; manual review required.")
                diff="\n".join(f"FILE: {f['filename']}\n{f.get('patch','[binary/large patch omitted]')}" for f in files)
                if len(diff)>180000:raise ValueError("Review diff exceeds the complete-review limit; split the work item.")
                kv(key,{"revision":item["head_sha"],"time":time.time(),"diff":diff},True)
                client.dispatch("agent-control.yml",{"action":"worker","role":"review","task-id":f"{release['id']}:{item['kind']}:{item['id']}","revision":item["head_sha"]});scheduled.append(key)
            if not kv("ci-queued:"+item["head_sha"]):
                kv("ci-queued:"+item["head_sha"],{"pr":pr["number"],"time":time.time()},True)
                client.dispatch("infrastructure-ci.yml",{"pull-request":str(pr["number"]),"revision":item["head_sha"]})
            if p["authority"]["merge_enabled"] and not kv("protected:"+item["pr_url"]):
                try:
                    # Dry precondition: inspect signed exact-revision review/CI
                    # facts before allowing any GitHub merge side effect.
                    import sqlite3
                    db=sqlite3.connect(DB);db.row_factory=sqlite3.Row
                    try:control._pr_ready(db,item)
                    finally:db.close()
                    current_pr=client.pr(pr["number"])
                    if current_pr["head"]["sha"]!=item["head_sha"]:continue
                    _,now_protected=pr_files(client,current_pr,item,p)
                    if now_protected:continue
                    merged=client.request("PUT",client.root+f"/pulls/{pr['number']}/merge",{"sha":item["head_sha"],"merge_method":"squash"})
                    if merged.get("merged"):control.integrate(release["id"],item["id"],item["head_sha"],merged["sha"],"github:merge",kind=item["kind"])
                except ControlError:pass
        for item in control.ready_items(release["id"]):
            role=item["scope"].get("role","coding");reference=f"{release['id']}:{item['kind']}:{item['id']}";key="queue:"+role+":"+reference
            queued=kv(key)
            if queued and queued.get("time",0)>time.time()-1800:continue
            if item["scope"].get("kind")!="infrastructure" and not p["checks"]["application_configured"]:continue
            info=client.info();base=item.get("head_sha") or client.request("GET",client.root+"/git/ref/heads/"+info["default_branch"])["object"]["sha"]
            kv(key,{"revision":base,"time":time.time()},True);client.dispatch("agent-control.yml",{"action":"worker","role":role,"task-id":reference,"revision":base});scheduled.append(key)
            break
        refreshed=control.snapshot(release["id"]);rel=refreshed["releases"][0];items=refreshed["items"]
        if rel['qa_passed'] and rel['integration_sha'] and rel['state'] in {'QA_PASSED','CANDIDATE_FROZEN'}:
            prepare_candidate(p,control,rel['id'],rel['integration_sha'],'controller:candidate')
        if rel['state']=='RELEASE_APPROVED' and p['authority']['production_release_enabled']:
            key='publish-queued:'+rel['id']+':'+rel['candidate_sha']
            if not kv(key):
                client.dispatch('release.yml',{'phase':'publish','candidate-id':rel['id'],'revision':rel['candidate_sha']})
                kv(key,{'queued':True},True)
        if items and all(i["status"] in {"INTEGRATED","DONE"} for i in items) and not rel["qa_passed"] and p["environment"]["staging"]["configured"] and p["checks"]["application_configured"]:
            revision=rel["integration_sha"];reference=f"{rel['id']}:story:{next(i['id'] for i in items if i['kind']=='story')}";key="queue:qa:"+reference;queued=kv(key)
            if not queued or queued.get("revision")!=revision:
                control.start_qa(rel["id"],revision,"controller:qa")
                kv(key,{"revision":revision,"time":time.time()},True)
                client.dispatch("staging-qa.yml",{"scope":"staging","task-id":reference,"revision":revision});scheduled.append(key)
    return {"worker_result":processed,"scheduled":scheduled}


def release(p,args):
    client=github(p);actor=principal(p,client)
    if actor not in p["founders"]["usernames"] and not (actor=='github-actions[bot]' and args.phase=='publish'):
        raise ValueError("Only a founder can request a candidate; publication needs recorded founder approval.")
    control=ledger(p);release_id=args.candidate_id
    if args.phase=="candidate":
        result,candidate=prepare_candidate(p,control,release_id,args.revision,actor)
        output("candidate-manifest.json",candidate)
        return {"candidate":result,"manifest_sha256":digest(candidate),"next":"Review and approve the release in the founder dashboard."}
    if not p["authority"]["production_release_enabled"]:raise ValueError("Production release is disabled until a real deployment adapter and founder policy are configured.")
    current=control.snapshot(release_id)["releases"][0]
    if current.get("release_approved_sha")!=args.revision or current.get("candidate_sha")!=args.revision:raise ValueError("Founder approval is missing or stale for this exact candidate.")
    manifest=kv("candidate:"+release_id);approval=kv("release-manifest-approval:"+release_id)
    if not manifest or not approval or digest(manifest)!=approval["manifest_hash"] or manifest["policy_sha256"]!=digest(p):raise ValueError("Candidate artifact/evidence/policy approval is missing or stale.")
    _,actual=current_plan(p,release_id)
    if current.get('plan_approved_hash')!=actual:raise ValueError('Plan approval is stale.')
    control.freeze_candidate(release_id,args.revision,actor)  # Recheck current CI/review/QA before publication.
    title=current["title"];notes="\n".join("- "+i["title"] for i in control.snapshot(release_id)["items"])
    tag="release-"+re.sub(r"[^A-Za-z0-9._-]","-",release_id)
    published=client.request("POST",client.root+"/releases",{"tag_name":tag,"target_commitish":args.revision,"name":title,"body":notes,"draft":False})
    return control.record_release(release_id,args.revision,"github-release:"+tag,{"github_release":published["html_url"],"changelog":notes},actor)


def parser():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="command",required=True)
    d=sub.add_parser("doctor");d.add_argument("--format",default="json")
    sub.add_parser("probe")
    v=sub.add_parser("validate");v.add_argument("--scope",default="infrastructure");v.add_argument("--revision")
    s=sub.add_parser("state");s.add_argument("--action",choices=["restore","save"],required=True)
    for name in ("event","reconcile"):
        x=sub.add_parser(name);x.add_argument("--event-path",default=os.environ.get("GITHUB_EVENT_PATH",""));x.add_argument("--event-name",default=os.environ.get("GITHUB_EVENT_NAME",""))
    w=sub.add_parser("worker");w.add_argument("--role",required=True);w.add_argument("--task-id",required=True);w.add_argument("--revision",required=True);w.add_argument("--event-path")
    a=sub.add_parser('approve');a.add_argument('--kind',choices=['plan','release'],required=True);a.add_argument('--release-id',required=True);a.add_argument('--expected-hash',required=True);a.add_argument('--revision',required=True)
    r=sub.add_parser("release");r.add_argument("--phase",choices=["candidate","publish"],required=True);r.add_argument("--candidate-id",required=True);r.add_argument("--revision",required=True)
    return p


def main(argv=None):
    args=parser().parse_args(argv);p=policy()
    try:
        if args.command=="doctor":result=doctor(p)
        elif args.command=="probe":result=probe(p)
        elif args.command=="validate":result=validate(p,args.scope,args.revision)
        elif args.command=="state":
            store=SnapshotStore(github(p),DB,os.environ.get("SDLC_STATE_SIGNING_KEY"),p["environment"]["remote_state"]["branch"])
            result=getattr(store,args.action)()
        elif args.command=="event":result=event(p,args)
        elif args.command=="worker":result=worker(p,args)
        elif args.command=='approve':result=approve(p,args)
        elif args.command=="reconcile":result=reconcile(p,args)
        else:result=release(p,args)
        print(json.dumps(result,indent=2));return 0
    except (ValueError,RuntimeError,KeyError,TypeError,OSError,ControlError,GitHubError) as error:
        print(json.dumps({"status":"BLOCKED","error":str(error)}),file=sys.stderr);return 1


if __name__=="__main__":raise SystemExit(main())
