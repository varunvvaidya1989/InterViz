"""Trusted API CI collection. Inputs are fetched by the controller, never workers.

Application checks use application-ci.yml; infrastructure remains a separate
requirement. Dispatch titles are accepted only with a controller queue receipt.
No persisted success is used as a substitute for a fresh complete API snapshot.
"""
import re

from .github import GitHubError


def workflows(p):
    result = {'infrastructure-ci.yml': list(p['gates']['required_infrastructure_status_checks'])}
    if p['checks']['application_configured']:
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


def collect(p, client, pr, queued):
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
                and pr.get('base', {}).get('repo', {}).get('full_name') == repository)
    evidence = {'repository': repository, 'pr': pr['number'], 'head': head, 'workflows': []}
    passed = valid_pr and (p['checks']['application_configured']
                          or not p['gates']['required_application_status_checks'])
    for filename, names in workflows(p).items():
        path = '.github/workflows/' + filename
        expected = client.request('GET', client.root + '/actions/workflows/' + filename)
        blob = client.file(path, branch)['sha']
        facts = {'workflow_id': expected['id'], 'path': path, 'workflow_blob': blob, 'required': names}
        evidence['workflows'].append(facts)
        candidates = []
        for summary in client.pages(client.root + '/actions/workflows/' + filename + '/runs', key='workflow_runs'):
            target, numbers = target_pr(summary, queued)
            if target == head and pr['number'] in numbers:
                candidates.append(summary)
        if not candidates:
            facts['result'] = 'missing'; passed = False; continue
        latest = max(candidates, key=lambda r: (r.get('run_number', 0), r['id'], r.get('run_attempt', 0)))
        run = client.request('GET', client.root + '/actions/runs/' + str(latest['id']))
        attempt = run.get('run_attempt')
        facts.update(run_id=run.get('id'), attempt=attempt, status=run.get('status'), conclusion=run.get('conclusion'))
        target, numbers = target_pr(run, queued)
        trusted = (run.get('id') == latest['id'] and type(attempt) is int and attempt > 0
                   and target == head and pr['number'] in numbers
                   and run.get('workflow_id') == expected['id'] and run.get('path') == path
                   and run.get('repository', {}).get('full_name') == repository
                   and run.get('head_repository', {}).get('full_name') == repository
                   and expected.get('path') == path
                   and (run.get('event') != 'workflow_dispatch' or run.get('head_branch') == branch)
                   and client.file(path, head)['sha'] == blob
                   and client.file(path, run['head_sha'])['sha'] == blob)
        jobs = client.pages(client.root + f"/actions/runs/{run['id']}/attempts/{attempt}/jobs", key='jobs') if trusted else []
        facts['jobs'] = jobs
        ok = trusted and bool(names) and run.get('status') == 'completed' and run.get('conclusion') == 'success'
        for name in names:
            matches = [j for j in jobs if j.get('name') == name]
            ok = ok and len(matches) == 1 and all(
                j.get('run_id') == run['id'] and j.get('run_attempt') == attempt
                and type(j.get('id')) is int and j.get('status') == 'completed'
                and j.get('conclusion') == 'success' for j in matches)
        # Re-read to detect a rerun starting while jobs were fetched.
        current = client.request('GET', client.root + '/actions/runs/' + str(latest['id']))
        ok = ok and current == run
        facts['result'] = 'success' if ok else 'untrusted_or_unsuccessful'
        passed = passed and ok
    current = client.pr(pr['number'])
    passed = passed and current['head']['sha'] == head
    return bool(passed), evidence


def reconcile_item(p, client, control, item, queued):
    pr = client.pr(int(item['pr_url'].rsplit('/', 1)[1]))
    if pr['head']['sha'] != item['head_sha']:
        control.associate_pr(item['release_id'], item['id'], pr['head']['sha'], pr['html_url'],
                             pr['user']['login'], 'github:head-update', kind=item['kind'])
        return
    try:
        passed, evidence = collect(p, client, pr, queued)
    except (GitHubError, KeyError, TypeError, ValueError):
        # Incomplete/unavailable API facts revoke prior green as well. Do not
        # retain upstream bodies or credentials in the ledger.
        passed, evidence = False, {'head': item['head_sha'], 'result': 'unavailable_or_invalid_api_facts'}
    if item['scope'].get('kind') == 'application' and not p['checks']['application_configured']:
        passed = False
    control.record_ci(item['release_id'], item['id'], item['head_sha'], passed,
                      evidence, 'github:ci-aggregate', kind=item['kind'])
