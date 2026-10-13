"""Capture resource/runtime state and verify all pre-existing tracked files."""
import argparse
import hashlib
import json
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT/'evaluation/reports/hardening/A05/answerability-20261013'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase',choices=['before','after'])
    args = parser.parse_args()
    if args.phase=='before':
        files = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
        hashes = {f:digest(ROOT/f) for f in files if f and (ROOT/f).is_file()}
        (REPORT/'protected_before.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    else:
        hashes = json.loads((REPORT/'protected_before.json').read_text(encoding='utf-8'))
        changes = [f for f,h in hashes.items() if not (ROOT/f).exists() or digest(ROOT/f)!=h]
        allowed = {'agents/tools.py','agents/support_agent.py',
                   'docs/CartCare-Codex-Workbench.html','docs/cartcare-workbench-progress.json'}
        assert set(changes)<=allowed, changes
        (REPORT/'preservation.json').write_text(json.dumps({'tracked_checked':len(hashes),
            'changed':changes,'unexpected_changes':[],'protected_unchanged':len(hashes)-len(changes)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    state = {'at_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'executable':sys.executable,
             'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}
    try:
        with socket.create_connection(('127.0.0.1',8000),timeout=2):
            state['api_port_8000']='listening'
    except OSError as exc:
        state['api_port_8000']='not_connectable'
        state['api_probe_error_type']=type(exc).__name__
    result = subprocess.run(['docker','inspect','echomind-app','--format','{{.State.Status}} {{.State.Running}}'],
                            capture_output=True,text=True,timeout=10)
    state['docker_inspect']={'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
    # Read-only direct heartbeat, never instantiate KnowledgeBase/get_or_create.
    import httpx
    try:
        response = httpx.get('http://127.0.0.1:8001/api/v1/heartbeat',timeout=2,trust_env=False)
        state['chroma_heartbeat']={'http_status':response.status_code,'body':response.text}
    except httpx.HTTPError as exc:
        state['chroma_heartbeat']={'error_type':type(exc).__name__,'message':str(exc)}
    state['service_start_attempts']=0
    state['real_model_calls']=0
    (REPORT/f'environment_{args.phase}.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()
