"""Read-only local planning validation. No ledger, network or app execution."""
import hashlib
import json
from pathlib import Path
from automation.runtime import plan_document, validate_assignment

ROOT = Path(__file__).resolve().parents[3]
DIR = Path(__file__).resolve().parent

def main():
    policy = json.loads((ROOT/'automation/policy.json').read_text())
    plan, approval_hash = plan_document(DIR/'plan.json', policy, ROOT)
    ids = {s['id'] for s in plan['user_stories']}
    parents = {s['id']: s for s in plan['product_stories']}
    assert len(ids) == len(plan['user_stories'])
    assert plan['source']['specification_sha256'] == hashlib.sha256((ROOT/plan['source']['specification']).read_bytes()).hexdigest()
    graph = plan['delivery_tasks']['dependency_graph']
    ancestors = {}
    for s in plan['user_stories']:
        assert s['kind'] in {'application', 'infrastructure'}
        assert 0 < s['estimate_worker_minutes'] <= policy['limits']['max_task_minutes']
        assert s['role'] != 'qa'
        assert s['tests'] and len(s['acceptance']) >= 2
        validate_assignment(s['allowed_paths'], policy, infrastructure=s['kind']=='infrastructure')
        assert graph[s['id']] == s['depends_on']
        assert s['id'] in parents[s['parent_story']]['child_tasks']
        ancestors[s['id']] = set(s['depends_on'])
        for dep in s['depends_on']:
            assert dep in ancestors, 'Tasks must be topologically ordered'
            ancestors[s['id']].update(ancestors[dep])
    assert set(graph) == ids
    assert {c for p in parents.values() for c in p['child_tasks']} == ids
    assert all(not s['ledger_item'] for s in plan['delivery_tasks']['release_stages'])
    # Any overlapping write scopes must be transitively ordered.
    def overlap(a,b):
        a,b=a.rstrip('/'),b.rstrip('/')
        return a==b or a.startswith(b+'/') or b.startswith(a+'/')
    for i,a in enumerate(plan['user_stories']):
        for b in plan['user_stories'][i+1:]:
            if any(overlap(x,y) for x in a['allowed_paths'] for y in b['allowed_paths']):
                assert a['id'] in ancestors[b['id']]
    for file, expected in plan['supporting_documents'].items():
        path=ROOT/file
        assert path.resolve().is_relative_to(DIR)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, file
    assert plan['supporting_documents'], 'Supporting contracts must be bound'
    assert all(a['status']=='NOT_RUN' for a in plan['acceptance_tests'])
    print(json.dumps({'status':'PASS','tasks':len(ids),'graph':'acyclic','paths':'policy-valid','overlapping_ownership':'serialized','supporting_digests':'match','approval_hash':approval_hash}))

if __name__ == '__main__': main()
