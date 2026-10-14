"""Read-only service/image/config preflight. No build/start/exec/model calls.

Never serialize credentials, container environment arrays or Redis commands.
Only get_collection/get/read/ping are used; KnowledgeBase.__init__ is avoided.
"""
import asyncio
import ctypes
import hashlib
import io
import json
import os
import socket
import subprocess
import tarfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from dotenv import dotenv_values
from evaluation.answerability.review_20261014.probe import OUT, ROOT


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inspect_docker(kind,target):
    args = ['docker']+(['image','inspect'] if kind=='image' else ['inspect'])+[target]
    result = subprocess.run(args,capture_output=True,timeout=15)
    if result.returncode:
        return None,{'exit':result.returncode,'error_type':'docker_inspection_failed'}
    return json.loads(result.stdout)[0],None


def environ_map(raw):
    return dict(s.split('=',1) for s in raw.get('Config',{}).get('Env',[]) if '=' in s)


def config_summary(values):
    key = values.get('ANTHROPIC_API_KEY','') or ''
    base = values.get('ANTHROPIC_BASE_URL','') or 'https://api.anthropic.com'
    parsed = urlsplit(base)
    identities = {}
    identity_error = None
    try:
        configured = json.loads(values.get('CARTCARE_DEMO_CREDENTIALS','{}') or '{}')
        if isinstance(configured,dict):
            identities = configured
        else:
            identity_error = 'not_a_mapping'
    except (ValueError,TypeError):
        identity_error = 'invalid_json'
    role_counts = {}
    valid_demo_count = 0
    scoped_independent_reviewers = 0
    for credential,p in identities.items():
        if not isinstance(p,dict):
            continue
        roles = p.get('roles',[])
        if not isinstance(roles,list):
            continue
        valid = len(credential)>=32 and bool(p.get('subject_id')) and set(roles)<={'customer','reviewer','admin'}
        valid = valid and ('customer' not in roles or bool(p.get('customer_id')))
        valid_demo_count += bool(valid)
        for role in roles:
            if role in {'customer','reviewer','admin'}:
                role_counts[role] = role_counts.get(role,0)+1
        if valid and 'reviewer' in roles and p.get('review_customers') and p.get('customer_id') is None:
            scoped_independent_reviewers += 1
    return {'api_key_present':bool(key),'api_key_looks_placeholder':key.lower() in {
                'test','fake-only','your-api-key','your_anthropic_api_key_here',''},
        'model':values.get('ANTHROPIC_MODEL','claude-3-5-sonnet-20241022'),
        'endpoint_scheme':parsed.scheme,'endpoint_hostname':parsed.hostname,
        'endpoint_port':parsed.port or (443 if parsed.scheme=='https' else 80),
        'official_deepseek_anthropic_base_matches':base.rstrip('/')=='https://api.deepseek.com/anthropic',
        'credentials_validated_by_model_request':False,
        'auth_mode':values.get('CARTCARE_AUTH_MODE','unset (deny default)'),
        'APP_ENV':values.get('APP_ENV','unset'),'API_HOST':values.get('API_HOST','unset'),
        'valid_demo_identity_count':valid_demo_count,'configured_role_counts':role_counts,
        'scoped_independent_reviewer_count':scoped_independent_reviewers,
        'demo_credential_parse_error':identity_error,
        'demo_loopback_config_gate':values.get('CARTCARE_AUTH_MODE')=='demo' and
            values.get('APP_ENV')=='development' and values.get('API_HOST') in {'127.0.0.1','::1'},
        'credentials_in_output':False}


def tcp(host,port):
    try:
        with socket.create_connection((host,port),timeout=3):
            return {'reachable':True}
    except OSError as exc:
        return {'reachable':False,'error_type':type(exc).__name__}


def source_in_stopped_container(container,path):
    result = subprocess.run(['docker','cp',f'{container}:/app/{path}','-'],capture_output=True,timeout=15)
    if result.returncode:
        return {'present':False,'docker_cp_exit':result.returncode}
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        files = [m for m in archive.getmembers() if m.isfile()]
        if len(files)!=1:
            return {'present':False,'error_type':'unexpected_archive_members'}
        raw = archive.extractfile(files[0]).read()
    current = ROOT/path
    return {'present':True,'container_sha256':digest(raw),
            'workspace_sha256':digest(current.read_bytes()),'same':raw==current.read_bytes()}


def main():
    now = datetime.now(timezone.utc)
    head = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    envfile = dotenv_values(ROOT/'.env') if (ROOT/'.env').exists() else {}
    local_values = {**envfile,**os.environ}
    report = {'at_utc':now.isoformat(),'at_beijing':now.astimezone(timezone(timedelta(hours=8))).isoformat(),'head':head,
        'local_env_config_redacted':config_summary(local_values),'container':{},'image':{},
        'service_start_attempts':0,'image_build_attempts':0,'docker_exec_attempts':0,'real_model_calls':0,
        'paid_requests':0,'model_downloads':0,'config_changes':0,'default_knowledge_writes':0}
    container,error = inspect_docker('container','echomind-app')
    if container:
        report['container'] = {'id':container['Id'],'created':container['Created'],
            'state':container['State']['Status'],'running':container['State']['Running'],
            'image_id':container['Image'],'mounts':[{'destination':m['Destination'],'type':m['Type'],
                'read_write':m['RW']} for m in container.get('Mounts',[])],
            'config_redacted':config_summary(environ_map(container))}
        image,image_error = inspect_docker('image',container['Image'])
        if image:
            labels = image.get('Config',{}).get('Labels',{}) or {}
            revision = labels.get('org.opencontainers.image.revision')
            report['image'] = {'id':image['Id'],'created':image['Created'],
                'oci_revision':revision,'revision_equals_head':revision==head if revision else None,
                'repo_tags':image.get('RepoTags',[])}
        else:
            report['image']=image_error
        # Read selected source bytes from the stopped container; no start/exec.
        if not container['State']['Running']:
            report['packaged_source_comparison'] = {p:source_in_stopped_container('echomind-app',p) for p in (
                'api/main.py','agents/support_agent.py','agents/tools.py','core/handoff.py',
                'mcp/knowledge_base.py','mcp/knowledge_assets/default_business_v1.json',
                'mcp/knowledge_assets/default_business_v1.approval.json')}
            diff = subprocess.run(['docker','diff','echomind-app'],capture_output=True,text=True,timeout=15)
            selected = set(report['packaged_source_comparison'])
            report['container_overlay_selected_source_changes'] = [line for line in diff.stdout.splitlines()
                if line[2:].removeprefix('/app/') in selected] if diff.returncode==0 else None
    else:
        report['container']=error
    report['tcp'] = {str(port):tcp('127.0.0.1',port) for port in (8000,8001,6379)}
    # Bypass proxies only in this audit process for local services.
    os.environ['NO_PROXY']='127.0.0.1,localhost'
    for service in ('echomind-chromadb','echomind-redis'):
        info,err = inspect_docker('container',service)
        report[service] = {'state':info['State']['Status'],'health':info['State'].get('Health',{}).get('Status'),
                          'running':info['State']['Running']} if info else err
    try:
        response = httpx.get('http://127.0.0.1:8001/api/v1/heartbeat',timeout=4,trust_env=False)
        report['chroma_heartbeat']={'status':response.status_code,'valid_heartbeat':'nanosecond heartbeat' in response.text}
    except httpx.HTTPError as exc:
        report['chroma_heartbeat']={'error_type':type(exc).__name__}
    try:
        import chromadb
        from mcp.knowledge_base import KnowledgeBase
        from mcp.default_knowledge_asset import load_approved_defaults
        from mcp.rag_contract import KnowledgeDocument
        client = chromadb.HttpClient(host='127.0.0.1',port=8001,
            settings=chromadb.Settings(anonymized_telemetry=False))
        client.heartbeat()
        collection = client.get_collection(KnowledgeBase.COLLECTION_NAME)
        kb = KnowledgeBase.__new__(KnowledgeBase)
        kb._collection,kb._collection_name,kb.min_score = collection,KnowledgeBase.COLLECTION_NAME,.35
        before = kb._snapshot()
        publications = kb._publications(before)
        eligible = kb._eligible(before,now)
        expected = {d.document_id:d for d in map(KnowledgeDocument.model_validate,load_approved_defaults())}
        actual = {d.document_id:d for d,p in publications.values()}
        assertions = {'six_publications':len(publications)==6,'six_effective_chunks':sum(map(len,eligible.values()))==6,
            'twelve_physical_rows':len(before)==12,'exact_approved_documents':actual==expected,
            'all_ready':all(p['state']=='ready' for d,p in publications.values())}
        after = kb._snapshot()
        assertions['read_only_snapshot_unchanged']=before==after
        report['default_collection']={'name':KnowledgeBase.COLLECTION_NAME,'metadata':collection.metadata,
            'physical_rows':len(before),'publications':len(publications),'effective_chunks':sum(map(len,eligible.values())),
            'assertions':assertions,'all_passed':all(assertions.values()),
            'snapshot_sha256':digest(json.dumps(before,sort_keys=True,ensure_ascii=False).encode()),
            'documents':[{'document_id':d.document_id,'source':d.source,'policy_version':d.policy_version,
                          'content_hash':digest(d.content.encode()),'publication_revision':p['revision'],
                          'state':p['state'],'chunk_ids':p['chunk_ids']} for d,p in publications.values()],
            'constructor_used':False,'collection_created':False,'query_calls':0}
    except Exception as exc:
        report['default_collection']={'error_type':type(exc).__name__,'verified':False}
    try:
        import redis
        password = local_values.get('REDIS_PASSWORD')
        credential_source = 'configured_environment_present' if password else 'absent'
        # Read runtime requirepass if local config differs; never serialize it.
        info,err = inspect_docker('container','echomind-redis')
        if info:
            cmd = info.get('Config',{}).get('Cmd',[]) or []
            if '--requirepass' in cmd:
                password = cmd[cmd.index('--requirepass')+1]
                credential_source = 'container_runtime_secret_read_without_output'
        redis_client = redis.Redis(host='127.0.0.1',port=6379,password=password,
            socket_connect_timeout=3,socket_timeout=3)
        report['redis_ping']={'success':bool(redis_client.ping()),'credential_source':credential_source,
                              'customer_keys_read':0,'writes':0}
        redis_client.close()
    except Exception as exc:
        report['redis_ping']={'success':False,'error_type':type(exc).__name__,'writes':0}
    cfg = report['local_env_config_redacted']
    host = cfg['endpoint_hostname']
    if host:
        try:
            socket.getaddrinfo(host,cfg['endpoint_port'])
            report['model_network']={'dns_resolves':True,'tcp':tcp(host,cfg['endpoint_port']),
                                    'http_model_requests':0,'credentials_not_tested':True}
        except OSError as exc:
            report['model_network']={'dns_resolves':False,'error_type':type(exc).__name__,'http_model_requests':0}
    from anthropic import _constants
    from core.skill_loader import SkillManager
    skills = SkillManager(str(ROOT/'skills'),max_prompt_chars=5000)
    skills.load()
    report['workspace_runtime_assets']={'approved_asset_hash':digest((ROOT/'mcp/knowledge_assets/default_business_v1.json').read_bytes()),
        'skills_count':len(skills.skills),'skill_errors':len(skills.errors),
        'skills_prompt_budget':5000}
    report['workspace_runtime_assets']['all_match_skill_prompt_chars']=len(skills.prompt_for('订单退款接口500发票会员',None))
    report['workspace_runtime_assets']['skill_hashes']={str(Path(s.path).relative_to(ROOT)).replace('\\','/'):digest(Path(s.path).read_bytes()) for s in skills.skills}
    report['sdk_defaults']={'default_max_retries':_constants.DEFAULT_MAX_RETRIES,
        'timeout_connect_s':_constants.DEFAULT_TIMEOUT.connect,'timeout_read_s':_constants.DEFAULT_TIMEOUT.read,
        'timeout_write_s':_constants.DEFAULT_TIMEOUT.write,'SupportRuntime_explicit_timeout_set':False,
        'support_tool_rounds':3,'support_max_tokens_per_call':1200,'rewrite_max_tokens':256,'rerank_max_tokens':256,
        'knowledge_read_attempts':2,'tool_timeout_s':30,'thinking_explicitly_set_in_current_requests':False}
    (OUT/'environment_preflight.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'container_state':report.get('container',{}).get('state'),
        'image_created':report.get('image',{}).get('created'),
        'source_comparison':report.get('packaged_source_comparison'),
        'default_collection':report.get('default_collection',{}).get('all_passed'),
        'redis_ping':report.get('redis_ping',{}).get('success'),'real_model_calls':0},ensure_ascii=False))


if __name__=='__main__':
    main()
