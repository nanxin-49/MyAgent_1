"""Authorized PR operations using existing Git credentials, never printing secrets."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = 'nanxin-49/MyAgent_1'
env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
credential = subprocess.run(['git', 'credential', 'fill'],
    input='protocol=https\nhost=github.com\npath=nanxin-49/MyAgent_1.git\n\n',
    text=True, capture_output=True, check=True, env=env)
fields = dict(line.split('=', 1) for line in credential.stdout.splitlines() if '=' in line)
token = fields.get('password')
if not token:
    raise RuntimeError('Existing Git credential unavailable')

def api(path, method='GET', body=None):
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + path,
        data=None if body is None else json.dumps(body).encode(), method=method,
        headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'CartCare-stage-merge',
                 'Content-Type': 'application/json'})
    for attempt in range(3 if method == 'GET' else 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            error = json.loads(exc.read())
            print(json.dumps({'http_status': exc.code, 'message': error.get('message'),
                              'errors': error.get('errors')}, ensure_ascii=False))
            sys.exit(1)
        except urllib.error.URLError:
            if method != 'GET' or attempt == 2:
                print(json.dumps({'error': 'GitHub transport failure', 'outcome_unknown': method != 'GET'}))
                sys.exit(1)
            time.sleep(2)

command = sys.argv[1]
if command == 'create':
    existing = api('/pulls?state=open&head=nanxin-49:codex/cartcare-single-memory-demo&base=main')
    result = existing[0] if existing else api('/pulls', 'POST', {
        'title': 'CartCare: adopt Single Agent, bound memory, and finish traceable demo',
        'head': 'codex/cartcare-single-memory-demo', 'base': 'main',
        'body': Path('data/stage-pr-body.md').read_text(encoding='utf-8'), 'draft': False})
    print(json.dumps({key: result.get(key) for key in ['number','html_url','state','mergeable','draft']}))
elif command == 'status':
    number = int(sys.argv[2]); pr = api(f'/pulls/{number}'); sha = pr['head']['sha']
    checks = api(f'/commits/{sha}/check-runs'); runs = api(f'/actions/runs?head_sha={sha}')
    print(json.dumps({'number': number, 'url': pr['html_url'], 'head_sha': sha,
        'state': pr['state'], 'merged': pr['merged'], 'merge_commit_sha': pr['merge_commit_sha'],
        'mergeable': pr['mergeable'], 'mergeable_state': pr['mergeable_state'],
        'checks': [{k:c.get(k) for k in ['id','name','status','conclusion','html_url']} for c in checks['check_runs']],
        'runs': [{k:r.get(k) for k in ['id','name','status','conclusion','event','html_url']} for r in runs['workflow_runs']]},ensure_ascii=False))
elif command == 'merge':
    number = int(sys.argv[2]); sha = sys.argv[3]
    pr = api(f'/pulls/{number}')
    assert pr['base']['ref'] == 'main' and pr['head']['sha'] == sha
    checks = api(f'/commits/{sha}/check-runs')['check_runs']
    assert any(c['name'] == 'Python 3.12 tests' and c['conclusion'] == 'success' for c in checks)
    assert all(c['status'] == 'completed' and c['conclusion'] in ['success','neutral','skipped'] for c in checks)
    print(json.dumps(api(f'/pulls/{number}/merge','PUT',{'sha': sha, 'merge_method':'merge',
        'commit_title': f'Merge CartCare Single Agent, Memory and Demo stage (#{number})'})))
