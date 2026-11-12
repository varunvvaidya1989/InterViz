"""Serve the founder dashboard on loopback; GitHub credentials stay server-side."""
import argparse
import base64
import concurrent.futures
import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from automation.github import GitHub, GitHubError, local_git_credential, verify_snapshot
from automation.approvals import approval_cards, intent_id, validate_intent
from automation.runtime import digest

ROOT = Path(__file__).resolve().parent


def stamp():
    return datetime.now(timezone.utc).isoformat()


def read_ledger(envelope, signing_key=None):
    """Inspect a separate in-memory copy; never open/mutate the controller DB."""
    if envelope.get('version') != 1 or len(envelope.get('database', '')) > 40_000_000:
        raise ValueError('Unsupported or oversized ledger snapshot.')
    data = base64.b64decode(envelope['database'], validate=True)
    if hashlib.sha256(data).hexdigest() != envelope.get('sha256'):
        raise ValueError('Ledger snapshot checksum failed.')
    if signing_key:
        verify_snapshot(envelope, signing_key)
    if not data.startswith(b'SQLite format 3\x00'):
        raise ValueError('Snapshot is not a SQLite database.')
    # A complete SQLite backup may retain WAL-mode header bytes. In-memory
    # deserialize cannot open a WAL sidecar; adjust only the private copy.
    data = data[:18] + b'\x01\x01' + data[20:]
    db = sqlite3.connect(':memory:')
    try:
        db.deserialize(data)
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA query_only=ON')
        db.row_factory = sqlite3.Row
        releases = [dict(r) for r in db.execute('SELECT id,title,state,plan_hash,plan_approved_hash,plan_approved_by,qa_passed,qa_sha,candidate_sha,release_approved_sha,integration_sha,created_at,updated_at FROM releases')]
        items = [dict(r) for r in db.execute('SELECT release_id,kind,id,title,scope,depends_on,status,head_sha,epoch,pr_url,attempts,max_attempts,lease_until,lease_started,lease_worker,updated_at FROM items')]
        for item in items:
            item['scope'] = json.loads(item['scope'])
            item['depends_on'] = json.loads(item['depends_on'])
        kv = {r['key']: json.loads(r['value']) for r in db.execute("SELECT key,value FROM runtime_kv WHERE key LIKE 'plan:%' OR key LIKE 'candidate:%' OR key LIKE 'release-manifest-approval:%' OR key LIKE 'work-issue:%' OR key LIKE 'bug-issue:%' OR key LIKE 'queue:%'")}
        reviews = [dict(r) for r in db.execute('SELECT release_id,kind,item_id,head_sha,epoch,verdict,evidence,created_at FROM reviews ORDER BY seq')]
        events = [dict(r) for r in db.execute('SELECT release_id,type,actor,created_at FROM events ORDER BY seq DESC LIMIT 60')]
        return {'releases': releases, 'items': items, 'kv': kv, 'reviews': reviews, 'events': events,
                'verification': 'signature_verified' if signing_key else 'github_authenticated_checksum_verified'}
    finally:
        db.close()


def classify(item, release, items, review=None, application_configured=False, now=None, worker_active=None):
    now = time.time() if now is None else now
    status = item['status']
    if status in ('DONE', 'INTEGRATED'):
        return 'integrated', 'Merged; release QA is a separate gate.'
    if status == 'IN_PROGRESS':
        if item.get('lease_until') and item['lease_until'] < now:
            return 'blocked', 'Worker lease expired; controller recovery is needed.'
        if worker_active is False and now - item.get('updated_at', now) > 90:
            return 'blocked', 'Task is leased but no worker workflow is active. Check the last run and controller recovery.'
        return 'running', 'A worker holds the task lease.'
    if status == 'OPEN' and item['attempts'] >= item['max_attempts']:
        return 'blocked', 'Attempt limit reached; lead intervention is required.'
    if (review and review['verdict'] == 'REQUEST_CHANGES' and review['head_sha'] == item.get('head_sha')
            and review.get('epoch',0)==item.get('epoch',0)):
        return 'rework', 'Independent reviewer requested changes.'
    if status == 'SUBMITTED':
        return 'reviewing', 'PR submitted; waiting for review, CI or integration.'
    if not release.get('plan_approved_hash') or release.get('plan_approved_hash') != release.get('plan_hash'):
        return 'blocked', 'Waiting for founder approval of the current plan.'
    unfinished = [dep for dep in item['depends_on'] if items.get(dep, {}).get('status') not in ('DONE', 'INTEGRATED')]
    if unfinished:
        return 'waiting', 'Waiting for ' + ', '.join(unfinished)
    if item['scope'].get('kind') != 'infrastructure' and not application_configured:
        return 'blocked', 'Application checks must be configured before dispatch.'
    return 'ready', 'Dependencies satisfied; ready for controller dispatch.'


def approval_options(client, ledger=None, policy=None):
    """Fresh remote facts for display/preflight; only the hosted controller signs approval."""
    if ledger is None:
        envelope=json.loads(base64.b64decode(client.file('controller/state.json','sdlc-state')['content']))
        ledger=read_ledger(envelope,os.environ.get('SDLC_STATE_SIGNING_KEY'))
    if policy is None:
        policy=json.loads(base64.b64decode(client.file('automation/policy.json','main')['content']))
    actor=client.request('GET','/user')['login']
    founder=actor in policy['founders']['usernames']
    try:
        workflow=client.request('GET',client.root+'/actions/workflows/founder-approval.yml')
        available=workflow.get('state')=='active'
    except GitHubError as error:
        if error.status!=404:raise
        available=False
    revision=None
    for release in ledger['releases']:
        manifest=ledger['kv'].get('plan:'+release['id']) or {}
        if manifest.get('path') and not manifest.get('document'):
            if revision is None:revision=client.request('GET',client.root+'/commits/main')['sha']
            document=client.file(manifest['path'],revision)
            manifest['document']=json.loads(base64.b64decode(document['content']))
    confirmations=[]
    for release in ledger['releases']:
        release_id=release['id'];plan=ledger['kv'].get('plan:'+release_id) or {}
        if plan.get('hash') and release.get('plan_approved_hash')==plan['hash'] and (plan.get('revision') or revision):
            confirmations.append(intent_id({'kind':'plan','release_id':release_id,'expected_hash':plan['hash'],
                                            'revision':plan.get('revision') or revision}))
        candidate=ledger['kv'].get('candidate:'+release_id)
        approval=ledger['kv'].get('release-manifest-approval:'+release_id) or {}
        if candidate and approval.get('manifest_hash')==digest(candidate) and release.get('release_approved_sha')==candidate['commit_sha']:
            confirmations.append(intent_id({'kind':'release','release_id':release_id,'expected_hash':approval['manifest_hash'],
                                            'revision':candidate['commit_sha']}))
    runs=client.request('GET',client.root+'/actions/workflows/founder-approval.yml/runs?per_page=20')['workflow_runs'] if available else []
    return {'actor':actor,'can_approve':founder and available,'workflow_available':available,
            'cards':approval_cards(ledger,policy,revision),'confirmed_ids':confirmations,
            'runs':[{k:r.get(k) for k in ('display_title','created_at','status','conclusion','html_url')} for r in runs]}


class ApprovalRequests:
    def __init__(self):
        self.lock=threading.Lock()
        self.pending={}

    def snapshot(self,data=None):
        with self.lock:
            if data and 'approvals' in data:
                options=data['approvals'];cards={c['id'] for c in options['cards']}
                for key,request in self.pending.items():
                    if key in options.get('confirmed_ids',[]):request['state']='confirmed'
                    elif key not in cards:request['state']='stale'
                    else:
                        title='Founder approval '+request['kind']+' '+request['release_id']+' '+request['expected_hash']+' '+request['revision']
                        runs=[r for r in options.get('runs',[]) if r['display_title']==title
                              and datetime.fromisoformat(r['created_at'].replace('Z','+00:00')).timestamp()>=request['requested_at']-5]
                        if runs:
                            run=runs[0];request['workflow_url']=run['html_url']
                            if run['status']=='completed' and run['conclusion']!='success':request['state']='failed'
                        if request['state']=='requested' and time.time()-request['requested_at']>900:request['state']='failed'
            return {key:dict(value) for key,value in self.pending.items()}

    def submit(self,client,intent):
        validate_intent(intent)
        # Re-read policy, identity and displayed targets immediately before dispatch.
        options=approval_options(client)
        if not options['can_approve']:
            raise PermissionError('Founder approval is not available for this account or controller version.')
        key=intent_id(intent)
        if key not in {card['id'] for card in options['cards']}:
            raise ValueError('This approval changed or was already recorded. Refresh the dashboard.')
        with self.lock:
            previous=self.pending.get(key)
            if previous and previous['state']=='requested' and time.time()-previous['requested_at']<900:
                return previous
            client.dispatch('founder-approval.yml',{'kind':intent['kind'],'release-id':intent['release_id'],
                                                  'expected-hash':intent['expected_hash'],'revision':intent['revision']})
            result={'state':'requested','requested_at':time.time(), 'release_id':intent['release_id'],
                    'expected_hash':intent['expected_hash'],'revision':intent['revision'],
                    'kind':intent['kind'],'workflow_url':'https://github.com/'+client.repository+'/actions/workflows/founder-approval.yml'}
            self.pending[key]=result
            return result


def collect(client):
    prefix = client.root
    calls = {
        'snapshot': lambda: client.file('controller/state.json', 'sdlc-state'),
        'issues': lambda: client.pages(prefix + '/issues?state=open'),
        'prs': lambda: client.pages(prefix + '/pulls?state=open'),
        'runs': lambda: client.request('GET', prefix + '/actions/runs?per_page=40')['workflow_runs'],
        'active_runs': lambda: client.request('GET', prefix + '/actions/runs?status=in_progress&per_page=100')['workflow_runs'],
        'policy': lambda: client.file('automation/policy.json', 'main'),
        'state_commits': lambda: client.request('GET', prefix + '/commits?sha=sdlc-state&path=controller/state.json&per_page=1'),
    }
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
        pending = {key: pool.submit(fn) for key, fn in calls.items()}
        sources = {key: future.result() for key, future in pending.items()}
    envelope = json.loads(base64.b64decode(sources['snapshot']['content']))
    ledger = read_ledger(envelope, os.environ.get('SDLC_STATE_SIGNING_KEY'))
    policy = json.loads(base64.b64decode(sources['policy']['content']))
    approvals=approval_options(client,ledger,policy)
    releases = ledger['releases']
    active_plans = {value.get('pr_url') for key, value in ledger['kv'].items() if key.startswith('plan:') and isinstance(value, dict)}
    item_urls = {i['pr_url'] for i in ledger['items'] if i['pr_url']}
    prs = [p for p in sources['prs'] if p['html_url'] in active_plans | item_urls]
    warnings = []

    def detail(pr):
        checks = client.request('GET', prefix + '/commits/' + pr['head']['sha'] + '/check-runs?per_page=100')
        comments = client.request('GET', prefix + '/issues/' + str(pr['number']) + '/comments?per_page=100')
        return {'number': pr['number'], 'title': pr['title'], 'url': pr['html_url'], 'head': pr['head']['sha'],
                'created_at': pr['created_at'], 'checks': [{'name': c['name'], 'status': c['status'], 'conclusion': c['conclusion'], 'url': c.get('html_url')} for c in checks['check_runs']],
                'review_comment': next((c['body'][:5000] for c in reversed(comments) if c['user']['login'] == 'github-actions[bot]' and 'Independent agent review' in c.get('body', '')), None),
                'plan': pr['html_url'] in active_plans}

    pr_details = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(detail, pr): pr for pr in prs[:30]}
        for future, pr in pending.items():
            try:
                pr_details.append(future.result())
            except Exception:
                warnings.append('Checks could not be loaded for PR #' + str(pr['number']))
    if len(prs) > 30:
        warnings.append('PR detail display is limited to 30 current PRs.')
    running_map = {r['id']:r for r in sources['runs'] if r['status'] in ('in_progress', 'queued', 'pending', 'waiting', 'requested')}
    running_map.update({r['id']:r for r in sources['active_runs']})
    running = list(running_map.values())
    run_details = []
    for run in running[:8]:
        try:
            jobs = client.request('GET', prefix + '/actions/runs/' + str(run['id']) + '/jobs')['jobs']
            step = next((s['name'] for j in jobs for s in j.get('steps', []) if s['status'] == 'in_progress'), 'Waiting for runner or workflow slot')
        except Exception:
            step = 'Step information unavailable'
        run_details.append({'id': run['id'], 'title': run['display_title'], 'status': run['status'], 'url': run['html_url'], 'started_at': run.get('run_started_at') or run['created_at'], 'step': step})
    review_map = {(r['release_id'], r['kind'], r['item_id']): r for r in ledger['reviews']}
    release_map = {r['id']: r for r in releases}
    tasks = []
    attention = []
    for item in ledger['items']:
        peers = {i['id']: i for i in ledger['items'] if i['release_id'] == item['release_id'] and i['kind'] == 'story'}
        review = review_map.get((item['release_id'], item['kind'], item['id']))
        if review and (review['head_sha']!=item.get('head_sha') or review.get('epoch')!=item.get('epoch')):
            review=None
        worker_active = any(r['status'] == 'in_progress' and r['name'] in ('SDLC - Agent control','SDLC - Staging QA','SDLC - Review and integration') for r in running)
        state, reason = classify(item, release_map[item['release_id']], peers, review, policy['checks']['application_configured'], worker_active=worker_active)
        scope = item['scope']
        key = 'work-issue:' + item['release_id'] + ':' + item['kind'] + ':' + item['id']
        issue_number = ledger['kv'].get(key) or ledger['kv'].get('bug-issue:' + item['id'])
        task = {k: item[k] for k in ('release_id', 'id', 'kind', 'title', 'status', 'attempts', 'max_attempts', 'pr_url', 'head_sha', 'depends_on', 'lease_until', 'lease_started', 'updated_at')}
        task.update(state=state, reason=reason, role=scope.get('role', 'coding'), category=scope.get('kind', 'application'),
                    acceptance=scope.get('acceptance', []), paths=scope.get('allowed_paths', []),
                    issue_url='https://github.com/' + client.repository + '/issues/' + str(issue_number) if issue_number else None,
                    review_summary=json.loads(review['evidence']).get('report', {}).get('summary') if review else None)
        tasks.append(task)
        if state in ('blocked', 'rework'):
            attention.append({'id': item['id'], 'release_id': item['release_id'], 'severity': 'high' if state == 'rework' or item['attempts'] else 'warning', 'title': item['id'] + ': ' + ('Changes requested' if state == 'rework' else 'Needs attention'), 'reason': reason, 'url': item['pr_url'] or task['issue_url']})
    for pr in pr_details:
        required = {'sdlc-infrastructure-ci', 'sdlc-independent-review'}
        names = {c['name'] for c in pr['checks']}
        failures = [c for c in pr['checks'] if c['conclusion'] in ('failure', 'timed_out', 'action_required', 'cancelled')]
        if pr['plan'] and 'sdlc-independent-review' not in names:
            attention.append({'id': 'plan-review-' + str(pr['number']), 'severity': 'warning', 'title': 'Planning PR needs independent review', 'reason': 'Required sdlc-independent-review check has not been reported on PR #' + str(pr['number']) + '.', 'url': pr['url']})
        elif failures:
            attention.append({'id': 'checks-' + str(pr['number']), 'severity': 'high', 'title': 'PR #' + str(pr['number']) + ' has unsuccessful checks', 'reason': ', '.join(c['name'] for c in failures), 'url': pr['url']})
    for run in running:
        started = datetime.fromisoformat((run.get('run_started_at') or run['created_at']).replace('Z','+00:00')).timestamp()
        if time.time() - started > 1800:
            attention.append({'id': 'long-run-' + str(run['id']), 'severity': 'warning', 'title': 'Workflow has been waiting or running for over 30 minutes', 'reason': run['display_title'], 'url': run['html_url']})
    relevant_pr_numbers = {p['number'] for p in pr_details}
    for run in sources['runs']:
        if run['conclusion'] == 'action_required' and any(p['number'] in relevant_pr_numbers for p in run.get('pull_requests', [])):
            attention.append({'id': 'approval-' + str(run['id']), 'severity': 'warning', 'title': 'Workflow needs maintainer approval', 'reason': run['display_title'], 'url': run['html_url']})
    current_issue_numbers = {int(t['issue_url'].rsplit('/', 1)[1]) for t in tasks if t['issue_url']}
    legacy = [i for i in sources['issues'] if 'pull_request' not in i and any(l['name'] in ('sdlc:story', 'sdlc:bug') for l in i['labels']) and i['number'] not in current_issue_numbers]
    for release in releases:
        release['plan_url'] = (ledger['kv'].get('plan:' + release['id']) or {}).get('pr_url')
    return {'repository': client.repository, 'fetched_at': stamp(), 'ledger_updated_at': sources['state_commits'][0]['commit']['committer']['date'] if sources['state_commits'] else None,
            'verification': ledger['verification'], 'releases': releases, 'tasks': tasks, 'pull_requests': pr_details, 'running': run_details,
            'recent_runs': [{'id': r['id'], 'title': r['display_title'], 'status': r['status'], 'conclusion': r['conclusion'], 'url': r['html_url'], 'created_at': r['created_at']} for r in sources['runs'][:20]],
            'attention': attention, 'events': ledger['events'], 'warnings': warnings, 'approvals':approvals,
            'legacy_issues': [{'number': i['number'], 'title': i['title'], 'url': i['html_url']} for i in legacy]}


class Cache:
    def __init__(self, factory, interval=60):
        self.factory, self.interval = factory, interval
        self.lock = threading.Lock()
        self.data, self.error, self.refreshing, self.attempted_at = None, None, False, None

    def refresh(self):
        with self.lock:
            if self.refreshing:
                return
            self.refreshing = True
        def work():
            try:
                data = collect(self.factory())
                with self.lock:
                    self.data, self.error = data, None
            except Exception as error:
                message = 'GitHub refresh failed. Check network connectivity and local GitHub authentication.'
                if isinstance(error, ValueError):
                    message = 'Controller snapshot could not be validated. The previous data is retained.'
                with self.lock:
                    self.error = message
            finally:
                with self.lock:
                    self.refreshing, self.attempted_at = False, stamp()
        threading.Thread(target=work, daemon=True).start()

    def snapshot(self):
        with self.lock:
            return {'data': self.data, 'error': self.error, 'refreshing': self.refreshing, 'attempted_at': self.attempted_at, 'refresh_interval': self.interval}


def make_server(cache,factory,port=8010):
    csrf_token=secrets.token_urlsafe(32)
    requests=ApprovalRequests()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, code, content, mime):
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(content)

        def local(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.local():
                self.send(403, b'Loopback access only.', 'text/plain'); return
            path = urlsplit(self.path).path
            if path == '/api/status':
                status=cache.snapshot()
                self.send(200, json.dumps({**status, 'csrf_token':csrf_token, 'approval_requests':requests.snapshot(status['data'])}).encode(), 'application/json'); return
            files = {'/en.json': ('en.json', 'application/json; charset=utf-8'), '/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if path not in files:
                self.send(404, b'Not found', 'text/plain'); return
            file, mime = files[path]
            self.send(200, (ROOT / 'static' / file).read_bytes(), mime)

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.local() or origin not in {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}:
                self.send(403, b'Local origin required.', 'text/plain'); return
            if self.path == '/api/refresh':
                cache.refresh()
                self.send(202, b'{"refreshing":true}', 'application/json'); return
            if self.path != '/api/approve':
                self.send(404, b'Not found', 'text/plain'); return
            if not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''),csrf_token):
                self.send(403, b'{"error":"invalid_session"}', 'application/json'); return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if self.headers.get('Content-Type')!='application/json' or not 0<length<=4096:
                    raise ValueError('Invalid body.')
                intent=json.loads(self.rfile.read(length))
                result=requests.submit(factory(),intent)
                cache.refresh()
                self.send(202,json.dumps(result).encode(),'application/json')
            except PermissionError:
                self.send(403,b'{"error":"founder_required"}','application/json')
            except (ValueError,TypeError,KeyError):
                self.send(409,b'{"error":"approval_changed"}','application/json')
            except Exception:
                self.send(502,b'{"error":"dispatch_failed"}','application/json')

    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8010)
    parser.add_argument('--repository', default='varunvvaidya1989/InterViz')
    parser.add_argument('--open-browser', action='store_true')
    args = parser.parse_args()
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN') or local_git_credential()
    if not token:
        raise SystemExit('Authenticate GitHub using Git Credential Manager or set GH_TOKEN locally. Never paste a token in chat.')
    cache = Cache(lambda: GitHub(args.repository, token=token))

    server = make_server(cache,cache.factory,args.port)
    cache.refresh()
    def pulse():
        while True:
            time.sleep(cache.interval)
            cache.refresh()
    threading.Thread(target=pulse, daemon=True).start()
    url = f'http://127.0.0.1:{args.port}'
    print('Founder dashboard: ' + url + ' (founder approvals enabled)', flush=True)
    if args.open_browser:
        webbrowser.open(url)
    server.serve_forever()


if __name__ == '__main__':
    main()
