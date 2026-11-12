"""Bounded, authenticated recovery evidence. Never execute or extract artifacts."""
import hashlib
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

from .providers import validate_report

MAX_ARCHIVE=10_000_000
MAX_RESULT=5_000_000


class ArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,message,headers,newurl):
        target=urllib.parse.urlsplit(newurl)
        if (target.scheme!='https' or target.username or target.password
                or not target.hostname or not target.hostname.endswith(('.blob.core.windows.net','.actions.githubusercontent.com'))):
            raise ValueError('Artifact redirect is outside the trusted download hosts.')
        redirected=super().redirect_request(request,fp,code,message,headers,newurl)
        redirected.remove_header('Authorization')
        return redirected


def download_artifact(client,artifact):
    if artifact.get('expired') or not 0<artifact.get('size_in_bytes',0)<=MAX_ARCHIVE:
        raise ValueError('Recovery artifact is missing, expired or oversized.')
    request=urllib.request.Request('https://api.github.com'+client.root+'/actions/artifacts/'+str(int(artifact['id']))+'/zip',
                                   headers={'Authorization':'Bearer '+client.token,'Accept':'application/vnd.github+json'})
    try:
        with urllib.request.build_opener(ArtifactRedirect()).open(request,timeout=45) as response:
            data=response.read(MAX_ARCHIVE+1)
    except (urllib.error.URLError,TimeoutError):
        raise ValueError('Recovery artifact could not be downloaded; upstream URLs are withheld.') from None
    if len(data)>MAX_ARCHIVE or artifact.get('digest')!='sha256:'+hashlib.sha256(data).hexdigest():
        raise ValueError('Recovery artifact digest or size is invalid.')
    return data


def read_result(data):
    if len(data)>MAX_ARCHIVE:raise ValueError('Recovery archive is oversized.')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members=[m for m in archive.infolist() if m.filename=='worker-result.json']
            if len(members)!=1 or members[0].file_size>MAX_RESULT:
                raise ValueError('Recovery needs one bounded worker-result.json.')
            result=json.loads(archive.read(members[0]))
    except (zipfile.BadZipFile,KeyError,UnicodeError,json.JSONDecodeError):
        raise ValueError('Recovery artifact is invalid.') from None
    return result


def unchanged_result(result,item,plan_hash):
    if not isinstance(result,dict):raise ValueError('Worker result must be an object.')
    expected=item['release_id']+':'+item['kind']+':'+item['id']
    if (result.get('reference')!=expected or result.get('kind')!=item['kind']
            or result.get('role')!=item['scope'].get('role','coding')
            or result.get('plan_hash')!=plan_hash or result.get('lease_id')!=item.get('lease_id')
            or result.get('worker_id')!=item.get('lease_worker')
            or result.get('changed_paths')!=[] or not isinstance(result.get('baseline'),dict)
            or not result['baseline'] or result['baseline']!=result.get('after')):
        raise ValueError('Worker result is not the exact unchanged leased resubmission.')
    report=validate_report(result.get('report'))
    if report['verdict']!='SUBMITTED':raise ValueError('An unsuccessful worker cannot be recovered as submitted.')
    return result


def retained_handoff(client,run,item,download=download_artifact):
    """Verify source run, task lease and digest before returning controller data."""
    info=client.info()
    workflow=client.request('GET',client.root+'/actions/workflows/agent-control.yml')
    if (run.get('workflow_id')!=workflow['id'] or run.get('path')!='.github/workflows/agent-control.yml'
            or run.get('head_branch')!=info['default_branch'] or run.get('event')!='workflow_dispatch'
            or run.get('status')!='completed' or run.get('conclusion')!='failure'
            or run.get('repository',{}).get('id')!=info['id']
            or run.get('head_repository',{}).get('id')!=info['id']):
        raise ValueError('Recovery source is not a failed trusted controller run.')
    jobs=client.request('GET',client.root+'/actions/runs/'+str(run['id'])+'/jobs')['jobs']
    steps=[s for job in jobs for s in job.get('steps',[])]
    if (not any(s['name']=='Execute queued Codex worker through isolated adapter' and s.get('conclusion')=='success' for s in steps)
            or not any(s['name']=='Reconcile policy and schedule permitted next work' and s.get('conclusion')=='failure' for s in steps)):
        raise ValueError('Source did not complete a worker followed by publication failure.')
    artifacts=client.request('GET',client.root+'/actions/runs/'+str(run['id'])+'/artifacts')['artifacts']
    name='sdlc-control-'+str(run['id'])+'-'+str(run['run_attempt'])
    artifacts=[a for a in artifacts if a.get('name')==name and not a.get('expired')]
    if len(artifacts)!=1:raise ValueError('Source has no unique retained controller artifact.')
    artifact=artifacts[0];provenance=artifact.get('workflow_run',{})
    if (provenance.get('id')!=run['id'] or provenance.get('head_sha')!=run['head_sha']
            or provenance.get('repository_id')!=info['id'] or provenance.get('head_repository_id')!=info['id']):
        raise ValueError('Artifact provenance does not match its trusted source run.')
    started=datetime.fromisoformat(run['run_started_at'].replace('Z','+00:00')).timestamp()
    completed=datetime.fromisoformat(run['updated_at'].replace('Z','+00:00')).timestamp()
    created=datetime.fromisoformat(artifact['created_at'].replace('Z','+00:00')).timestamp()
    if not started<=item['lease_started']<=created<=completed<=item['lease_until']:
        raise ValueError('Retained result did not complete within the interrupted task lease.')
    data=download(client,artifact)
    # Enforce the digest also for injected transports used by fixture tests.
    if artifact.get('digest')!='sha256:'+hashlib.sha256(data).hexdigest():
        raise ValueError('Recovery artifact digest does not match GitHub metadata.')
    result=read_result(data)
    return result,{'run_id':run['id'],'run_attempt':run['run_attempt'],'artifact_id':artifact['id'],
                   'artifact_digest':artifact['digest'],'url':run['html_url']}


def source_handoff(client,run,item,plan_hash,download=download_artifact):
    result,source=retained_handoff(client,run,item,download)
    return unchanged_result(result,item,plan_hash),source


def publication_handoff(client,run,item,plan_hash,download=download_artifact):
    """First publication uses retained source bytes, never unchanged recovery."""
    from .runtime import validate_source_bundle
    import re
    result,source=retained_handoff(client,run,item,download)
    expected=item['release_id']+':'+item['kind']+':'+item['id']
    if (not isinstance(result,dict) or result.get('reference')!=expected
            or result.get('kind')!=item['kind'] or result.get('role')!=item['scope'].get('role','coding')
            or result.get('role') not in {'coding','devops','ui-ux'}
            or result.get('plan_hash')!=plan_hash or result.get('worker_id')!=item.get('lease_worker')
            or result.get('lease_id')!=item.get('lease_id')
            or not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}',result.get('revision',''))
            or not isinstance(result.get('baseline'),dict) or not result['baseline']
            or not isinstance(result.get('after'),dict) or not result.get('changed_paths')):
        raise ValueError('Retained source does not match the original leased publication.')
    if validate_report(result.get('report'))['verdict']!='SUBMITTED':
        raise ValueError('Only successful submitted worker source can be published.')
    validate_source_bundle(result.get('source_bundle'),result['baseline'],result['after'],
                           result['changed_paths'],item['scope']['allowed_paths'])
    return result,source


def verified_pass_report(client,event,item,plan_hash,contract,download=download_artifact):
    """Recover a genuine positive review, never infer success from a job label."""
    evidence=event['payload'].get('evidence',{});report=evidence.get('report',{})
    if report.get('verdict')!='PASS' or report.get('findings')!=[] or evidence.get('contract')!=contract:
        raise ValueError('The source is not a positive current-contract review.')
    run_id=str(evidence.get('execution',''))
    if not run_id.isdigit():raise ValueError('Positive review lacks authenticated execution provenance.')
    run=client.request('GET',client.root+'/actions/runs/'+run_id)
    info=client.info();workflow=client.request('GET',client.root+'/actions/workflows/agent-control.yml')
    if (run.get('workflow_id')!=workflow['id'] or run.get('path')!='.github/workflows/agent-control.yml'
            or run.get('head_branch')!=info['default_branch'] or run.get('event')!='workflow_dispatch'
            or run.get('status')!='completed' or run.get('conclusion')!='success'
            or run.get('repository',{}).get('id')!=info['id'] or run.get('head_repository',{}).get('id')!=info['id']):
        raise ValueError('Positive review is not from a completed trusted controller execution.')
    artifacts=client.request('GET',client.root+'/actions/runs/'+run_id+'/artifacts')['artifacts']
    name='sdlc-control-'+run_id+'-'+str(run['run_attempt'])
    artifacts=[a for a in artifacts if a.get('name')==name and not a.get('expired')]
    if len(artifacts)!=1:raise ValueError('Positive review lacks a unique retained result.')
    artifact=artifacts[0];source=artifact.get('workflow_run',{})
    if (source.get('id')!=run['id'] or source.get('head_sha')!=run['head_sha']
            or source.get('repository_id')!=info['id'] or source.get('head_repository_id')!=info['id']):
        raise ValueError('Positive review artifact provenance is stale.')
    data=download(client,artifact)
    if artifact.get('digest')!='sha256:'+hashlib.sha256(data).hexdigest():raise ValueError('Positive review artifact digest failed.')
    result=read_result(data)
    if not isinstance(result,dict):raise ValueError('Positive review result must be an object.')
    validate_report(result.get('report'))
    if (result.get('role')!='review' or result.get('reference')!=item['release_id']+':'+item['kind']+':'+item['id']
            or result.get('revision')!=item['head_sha'] or result.get('worker_id')!=event['actor']
            or result.get('plan_hash')!=plan_hash or result.get('review_contract')!=contract
            or result.get('report')!=report or result.get('changed_paths')!=[]
            or not result.get('baseline') or result.get('baseline')!=result.get('after') or not report.get('evidence')):
        raise ValueError('Positive review result does not match its signed source, exact candidate and approved plan.')
    return {'report':report,'execution':run_id,'contract':contract,'verdict_alias':'PASS',
            'source_environment_event':event['seq'],'artifact_id':artifact['id'],
            'artifact_digest':artifact['digest'],'url':run['html_url']}
