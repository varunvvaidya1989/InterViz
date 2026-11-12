"""Trusted API CI collection. Inputs are fetched by the controller, never workers.

Application checks use application-ci.yml; infrastructure remains a separate
requirement. Dispatch titles are accepted only with a controller queue receipt.
No persisted success is used as a substitute for a fresh complete API snapshot.
"""
import re
from datetime import datetime

from .github import GitHubError


def workflows(p, application=True):
    result = {'infrastructure-ci.yml': list(p['gates']['required_infrastructure_status_checks'])}
    if application and p['checks']['application_configured']:
        result['application-ci.yml'] = list(p['gates']['required_application_status_checks'])
    return result


def target_pr(run, queued):
    if run.get('event') == 'pull_request':
        return run.get('head_sha'), [v['number'] for v in run.get('pull_requests', [])]
    if run.get('event') == 'workflow_dispatch':
        match = re.fullmatch(r'SDLC CI workflow_dispatch pr=(\d+) sha=([a-f0-9]{40,64})', run.get('display_title', ''))
        if match:
            number, head = int(match[1]), match[2]
            receipt = queued(head)
            if isinstance(receipt, dict) and receipt.get('pr') == number:
                return head, [number]
    return None, []


def latest_executions(client, filename, head, number, queued):
        candidates = []
        for summary in client.pages(client.root + '/actions/workflows/' + filename + '/runs', key='workflow_runs'):
            target, numbers = target_pr(summary, queued)
            if target != head or number not in numbers:
                continue
            # List responses can lag behind a rerun. Refresh every matching
            # run before selecting execution recency, not just the largest
            # creation-time run number.
            run = client.request('GET', client.root + '/actions/runs/' + str(summary['id']))
            if run.get('id') != summary['id']:
                raise ValueError('Run identity changed while collecting CI facts.')
            stamp = run.get('updated_at')
            if not isinstance(stamp, str):
                raise ValueError('Execution recency is unavailable.')
            updated = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if updated.tzinfo is None:
                raise ValueError('Execution recency must include a timezone.')
            candidates.append((updated.timestamp(), run))
        if not candidates:
            return []
        newest = max(stamp for stamp, _ in candidates)
        # GitHub timestamps have finite resolution. All executions tied for
        # newest must pass; a tied failed/cancelled rerun cannot inherit green.
        return sorted((run for stamp, run in candidates if stamp == newest), key=lambda run: run['id'])


def collect(p, client, pr, queued, application=True):
    """Return aggregate and auditable per-workflow/run/attempt/job facts.

    Select the newest run before checking its result, and fetch its current
    attempt again: reverse API ordering and delayed events cannot replay green.
    Workflow bytes must match both the default branch and actual execution SHA.
    """
    head = pr['head']['sha']
    repository = p['repository']['full_name']
    branch = client.info()['default_branch']
    valid_pr = (client.repository == repository
                and pr['head']['repo']['full_name'] == repository
                and pr.get('base', {}).get('repo', {}).get('full_name') == repository
                and pr.get('base', {}).get('ref') == branch)
    evidence = {'repository': repository, 'pr': pr['number'], 'head': head, 'workflows': []}
    passed = valid_pr and (not application or (p['checks']['application_configured']
                          and bool(p['gates']['required_application_status_checks'])))
    snapshots = []
    for filename, names in workflows(p, application).items():
        path = '.github/workflows/' + filename
        expected = client.request('GET', client.root + '/actions/workflows/' + filename)
        blob = client.file(path, branch)['sha']
        facts = {'workflow_id': expected['id'], 'path': path, 'workflow_blob': blob, 'required': names}
        evidence['workflows'].append(facts)
        selected = latest_executions(client, filename, head, pr['number'], queued)
        if not selected:
            facts['result'] = 'missing'; passed = False; continue
        snapshots.append((filename, selected, facts))
        facts['executions'] = []
        ok = True
        for run in selected:
            attempt = run.get('run_attempt')
            detail = {'run_id': run.get('id'), 'attempt': attempt, 'updated_at': run.get('updated_at'),
                      'status': run.get('status'), 'conclusion': run.get('conclusion')}
            facts['executions'].append(detail)
            target, numbers = target_pr(run, queued)
            trusted = (type(attempt) is int and attempt > 0
                       and target == head and pr['number'] in numbers
                       and run.get('workflow_id') == expected['id'] and run.get('path') == path
                       and run.get('repository', {}).get('full_name') == repository
                       and run.get('head_repository', {}).get('full_name') == repository
                       and expected.get('path') == path
                       and (run.get('event') != 'workflow_dispatch' or run.get('head_branch') == branch)
                       and client.file(path, head)['sha'] == blob
                       and client.file(path, run['head_sha'])['sha'] == blob)
            jobs = client.pages(client.root + f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", key='jobs') if trusted else []
            detail['jobs'] = jobs
            run_ok = trusted and bool(names) and run.get('status') == 'completed' and run.get('conclusion') == 'success'
            for name in names:
                matches = [j for j in jobs if j.get('name') == name]
                run_ok = run_ok and len(matches) == 1 and all(
                    j.get('run_id') == run['id'] and j.get('run_attempt') == attempt
                    and type(j.get('id')) is int and j.get('status') == 'completed'
                    and j.get('conclusion') == 'success' for j in matches)
            current = client.request('GET', client.root + '/actions/runs/' + str(run['id']))
            run_ok = run_ok and current == run
            detail['result'] = 'success' if run_ok else 'untrusted_or_unsuccessful'
            ok = ok and run_ok
        facts['result'] = 'success' if ok else 'untrusted_or_unsuccessful'
        passed = passed and ok
    # Validate the complete workflow set after ALL jobs, not one workflow
    # before later workflows have had a chance to start a rerun.
    for filename, selected, facts in snapshots:
        current_runs=latest_executions(client, filename, head, pr['number'], queued)
        if current_runs != selected:
            passed=False
            facts['result']='execution_changed_after_collection'
            facts['current_executions']=[{key:run.get(key) for key in
                ('id','run_attempt','updated_at','status','conclusion')} for run in current_runs]
    current = client.pr(pr['number'])
    passed = passed and current['head']['sha'] == head
    return bool(passed), evidence


def reconcile_item(p, client, control, item, queued, verified_pr=None):
    try:
        pr = verified_pr if verified_pr is not None else client.pr(int(item['pr_url'].rsplit('/', 1)[1]))
        repository = p['repository']['full_name']
        if (client.repository != repository or pr['head']['repo']['full_name'] != repository
                or pr['base']['repo']['full_name'] != repository
                or pr['base']['ref'] != client.info()['default_branch']):
            raise ValueError('PR repository/base facts do not match the approved target.')
        if pr['head']['sha'] != item['head_sha']:
            if item['status'] in {'INTEGRATED', 'DONE'}:
                passed, evidence = False, {'result': 'accepted_pr_head_changed', 'current_head': pr['head']['sha']}
            else:
                current = client.pr(pr['number'])
                if current['head'] != pr['head'] or current['base'] != pr['base']:
                    raise ValueError('PR changed after scope verification.')
                control.associate_pr(item['release_id'], item['id'], pr['head']['sha'], pr['html_url'],
                                     pr['user']['login'], 'github:head-update', kind=item['kind'])
                return
        else:
            passed, evidence = collect(p, client, pr, queued, application=item['scope'].get('kind') != 'infrastructure')
    except (GitHubError, KeyError, TypeError, ValueError):
        # Incomplete/unavailable API facts revoke prior green as well. Do not
        # retain upstream bodies or credentials in the ledger.
        passed, evidence = False, {'head': item['head_sha'], 'result': 'unavailable_or_invalid_api_facts'}
    if item['scope'].get('kind') == 'application' and not p['checks']['application_configured']:
        passed = False
    control.record_ci(item['release_id'], item['id'], item['head_sha'], passed,
                      evidence, 'github:ci-aggregate', kind=item['kind'])
