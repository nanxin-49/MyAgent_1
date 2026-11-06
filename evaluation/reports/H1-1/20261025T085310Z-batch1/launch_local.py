"""One-run launcher for current /chat, real SDK, isolated data and a wire budget."""
import argparse, asyncio, copy, hashlib, json, os, secrets, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
RUN = Path(__file__).resolve().parent
PRIVATE = ROOT / 'cash/h11-e2e-20261025'
sys.path.insert(0, str(ROOT))
def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def configure():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    os.environ.update(APP_ENV='development', API_HOST='127.0.0.1', API_PORT='8016',
        ANTHROPIC_BASE_URL='https://api.deepseek.com/anthropic',
        CARTCARE_AUTH_MODE='demo', CHROMA_HOST='127.0.0.1', CHROMA_PORT='8001',
        REDIS_URL='redis://127.0.0.1:6396/0', NO_PROXY='127.0.0.1,localhost',
        no_proxy='127.0.0.1,localhost', ALERT_WEBHOOK_URL='', PROMETHEUS_PORT='0',
        CARTCARE_H11_E2E='1',
        CARTCARE_RAG_MIN_SCORE='0.35', EVAL_BASELINE_PATH=str(PRIVATE / 'unused-eval.json'),
        ECHOMIND_SKILLS_DIR=str(ROOT / 'skills'), ECHOMIND_SKILLS_MAX_PROMPT_CHARS='5000',
        CARTCARE_BUSINESS_FIXTURE=str(RUN / 'fixture.json'))
    PRIVATE.mkdir(parents=True, exist_ok=True)
    credentials = PRIVATE / 'credentials.json'
    if not credentials.exists():
        identities = {}
        for label, identity in {
            'customer1': dict(subject_id='e2e-customer-1', customer_id='customer-1', roles=['customer']),
            'customer2': dict(subject_id='e2e-customer-2', customer_id='customer-2', roles=['customer']),
            'reviewer': dict(subject_id='e2e-reviewer', roles=['reviewer'], review_customers=['customer-1']),
            'admin': dict(subject_id='e2e-admin', roles=['admin'])}.items():
            identities[label] = dict(token=secrets.token_urlsafe(36), identity=identity)
        save(credentials, identities)
    identities = json.loads(credentials.read_text(encoding='utf-8'))
    os.environ['CARTCARE_DEMO_CREDENTIALS'] = json.dumps({v['token']: v['identity'] for v in identities.values()})
    return identities
def snapshot_knowledge():
    import chromadb
    from mcp.knowledge_base import KnowledgeBase
    from mcp.default_knowledge_asset import load_approved_defaults
    from mcp.rag_contract import KnowledgeDocument
    client = chromadb.HttpClient(host='127.0.0.1', port=8001, settings=chromadb.Settings(anonymized_telemetry=False))
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb._collection = client.get_collection(KnowledgeBase.COLLECTION_NAME)
    rows = kb._snapshot()
    pubs = kb._publications(rows)
    assert len(rows) == 12 and len(pubs) == 6 and len(kb._eligible(rows, datetime.now(timezone.utc))) == 6
    for doc in load_approved_defaults():
        parsed = KnowledgeDocument.model_validate(doc)
        stored, payload = pubs[kb._key(parsed)]
        assert stored == parsed and payload['state'] == 'ready'
    return dict(rows=rows, sha256=hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
        physical_rows=12, ready_publications=6, eligible_chunks=6, collection=KnowledgeBase.COLLECTION_NAME,
        heartbeat=client.heartbeat())
def prepare():
    import importlib.metadata as metadata, redis
    from core.skill_loader import SkillManager
    fixture = RUN / 'fixture.json'
    assert fixture.exists(), 'fixture.json missing; generate it before --prepare'
    kb = snapshot_knowledge()
    save(RUN / 'knowledge_before.json', kb)
    manager = SkillManager(str(ROOT / 'skills'), max_prompt_chars=5000)
    manager.load()
    assert not manager.errors and manager.summary()['count'] == 3
    rc = redis.Redis(host='127.0.0.1', port=6396)
    assert rc.ping()
    files = ['api/main.py','agents/support_agent.py','agents/agent_orchestrator.py','agents/tools.py',
        'core/handoff.py','core/auth.py','core/model_observation.py','mcp/tool_manager.py','mcp/knowledge_base.py',
        'memory/conversation_memory.py','pyproject.toml','uv.lock']
    files += [str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT / 'skills').rglob('SKILL.md')]
    manifest = dict(at_utc=datetime.now(timezone.utc).isoformat(),
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        initial_git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
        python=sys.version, source_sha256={p:sha(ROOT / p) for p in files}, fixture_sha256=sha(fixture),
        skills=manager.summary(), versions={p:metadata.version(p) for p in ['anthropic','httpx','uvicorn','fastapi','redis','chromadb-client']},
        config={k:os.environ[k] for k in ['APP_ENV','API_HOST','API_PORT','CARTCARE_AUTH_MODE','CHROMA_HOST','CHROMA_PORT',
            'REDIS_URL','CARTCARE_RAG_MIN_SCORE','CARTCARE_BUSINESS_FIXTURE']},
        principals={k:v['identity'] for k,v in configure().items()},
        model=os.environ.get('ANTHROPIC_MODEL'), endpoint=os.environ.get('ANTHROPIC_BASE_URL'),
        api_key_present=bool(os.environ.get('ANTHROPIC_API_KEY')), redis_ping=True, redis_size=rc.dbsize(),
        kb_sha256=kb['sha256'], model_requests=0, live_model_compatibility_verified=False,
        budget_authorization=dict(source='H1-1 approved plan 2026-10-25',usd_max=.10,requests_max=20),
        sdk_retries=0, request_timeout_seconds=60, thinking='disabled',
        memory_collections=['h11_e2e_20261025_topics','h11_e2e_20261025_profile'])
    assert manifest['model'] == 'deepseek-flash' and manifest['endpoint'] == 'https://api.deepseek.com/anthropic'
    save(RUN / 'environment.json', manifest)
    print('Preflight OK: current source; 6 approved active docs; 3 Skills; isolated Redis; zero model calls.')
def serve(enable_model):
    import anthropic, httpx
    ledger_path = RUN / 'model_ledger.json'
    ledger = json.loads(ledger_path.read_text(encoding='utf-8')) if ledger_path.exists() else dict(requests=0, charged_or_reserved_usd=0., events=[], halted=False)
    lock = asyncio.Lock()
    class BudgetTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.inner = httpx.AsyncHTTPTransport(retries=0)
        async def handle_async_request(self, request):
            async with lock:
                if not enable_model or ledger['halted']:
                    raise RuntimeError('Model gate closed')
                body = json.loads(request.content)
                assert request.url.host == 'api.deepseek.com' and request.url.path == '/anthropic/v1/messages'
                assert body['model'] == 'deepseek-flash' and not body.get('stream')
                assert body['max_tokens'] <= 1200 and body['thinking']['type'] == 'disabled'
                input_bound = len(request.content) + 8192
                assert input_bound <= 200000
                reserved = (input_bound*.30 + body['max_tokens']*1.20)/1_000_000
                if ledger['requests'] >= 20 or ledger['charged_or_reserved_usd'] + reserved > .10:
                    ledger['halted'] = True
                    save(ledger_path, ledger)
                    raise RuntimeError('Authorized request or cost budget exhausted')
                from core.model_observation import model_events
                observed = model_events.get() or []
                event = dict(number=ledger['requests']+1, at_utc=datetime.now(timezone.utc).isoformat(),
                    stage=observed[-1].get('stage') if observed else 'other_sdk', model=body['model'], reserved_usd=reserved,
                    tool_results_sent=[b for m in body.get('messages',[]) if isinstance(m.get('content'),list)
                        for b in m['content'] if isinstance(b,dict) and b.get('type')=='tool_result'])
                ledger['requests'] += 1
                ledger['charged_or_reserved_usd'] += reserved
                ledger['events'].append(event)
                save(ledger_path, ledger)
                start = time.monotonic()
                try:
                    response = await asyncio.wait_for(self.inner.handle_async_request(request),timeout=60)
                    await asyncio.wait_for(response.aread(),timeout=max(1,60-(time.monotonic()-start)))
                    event['http_status'] = response.status_code
                    if response.status_code != 200:
                        ledger['halted'] = True
                        event['error_type'] = 'provider_http_error'
                    else:
                        payload = response.json()
                        usage = payload.get('usage',{})
                        event.update(usage=usage, stop_reason=payload.get('stop_reason'),
                            content=[b for b in payload.get('content',[]) if b.get('type') in {'text','tool_use'}])
                        inp = sum(usage.get(k,0) or 0 for k in ['input_tokens','cache_read_input_tokens','cache_creation_input_tokens'])
                        out = usage.get('output_tokens')
                        if not isinstance(out,int) or not isinstance(usage.get('input_tokens'),int) or inp > input_bound or out > body['max_tokens']:
                            ledger['halted'] = True
                            event['error_type'] = 'usage_missing_or_exceeds_reservation'
                        else:
                            cost = (inp*.30 + out*1.20)/1_000_000
                            event['peak_cache_miss_cost_usd'] = cost
                            ledger['charged_or_reserved_usd'] += cost-reserved
                    return response
                except Exception as exc:
                    ledger['halted'] = True
                    event['error_type'] = type(exc).__name__
                    raise
                finally:
                    event['latency_ms'] = round((time.monotonic()-start)*1000,1)
                    save(ledger_path, ledger)
        async def aclose(self):
            await self.inner.aclose()
    original = anthropic.AsyncAnthropic
    class BoundedSDK(original):
        def __init__(self, **kwargs):
            kwargs.update(max_retries=0,timeout=httpx.Timeout(60,connect=5),
                http_client=httpx.AsyncClient(transport=BudgetTransport(),timeout=httpx.Timeout(60,connect=5),
                    follow_redirects=False,trust_env=False))
            super().__init__(**kwargs)
            create = self.messages.create
            async def nonthinking_create(**params):
                params['extra_body'] = {**params.get('extra_body',{}),'thinking':{'type':'disabled'}}
                return await create(**params)
            self.messages.create = nonthinking_create
    anthropic.AsyncAnthropic = BoundedSDK
    from memory.conversation_memory import MemoryManager
    MemoryManager.EPISODIC_COLLECTION = 'h11_e2e_20261025_topics'
    MemoryManager.PROFILE_COLLECTION = 'h11_e2e_20261025_profile'
    import mcp.knowledge_base as knowledge
    class ReadOnlyKnowledge(knowledge.KnowledgeBase):
        def _open_collection(self):
            col = self._client.get_collection(self._collection_name)
            assert col.metadata['embedding_version']=='char-bigram-1024-v1' and col.metadata['hnsw:space']=='cosine' and col.count()==12
            return col
        def _load_default_docs(self):
            raise RuntimeError('Knowledge seeding forbidden')
        def add_documents(self,*args,**kwargs):
            raise RuntimeError('Knowledge writes forbidden')
    knowledge.KnowledgeBase = ReadOnlyKnowledge
    from api import main
    import uvicorn
    if os.getenv('CARTCARE_H11_E2E') == '1':
        from fastapi import Depends
        from core.auth import require_admin

        @main.app.get('/__h11/state', dependencies=[Depends(require_admin)])
        def _h11_state():
            service = main._action_service
            return dict(
                business=copy.deepcopy(service._business_backend.state.data),
                handoffs=copy.deepcopy(main._orchestrator.handoff_service._records),
                actions={k: v.model_dump(mode='json') for k, v in service._store._actions.items()},
                executor_calls=len(service._executor._backend.calls),
            )

        @main.app.post('/__h11/state', dependencies=[Depends(require_admin)])
        def _h11_mutate(payload: dict):
            service = main._action_service
            data = service._business_backend.state.data
            for section in ('orders', 'shipments', 'inventory', 'refunds'):
                for key, value in (payload.get(section) or {}).items():
                    data.setdefault(section, {})
                    data[section].setdefault(key, {})
                    data[section][key].update(value)
            return dict(ok=True)
    chat_lock = asyncio.Lock()
    def state():
        service = main._action_service
        return dict(business=copy.deepcopy(service._business_backend.state.data) if service else None,
            handoffs=copy.deepcopy(main._orchestrator.handoff_service._records) if main._orchestrator else None,
            actions={k:v.model_dump(mode='json') for k,v in service._store._actions.items()} if service else None)
    @main.app.middleware('http')
    async def capture_state(request,call_next):
        if request.url.path!='/chat':
            return await call_next(request)
        async with chat_lock:
            number = len(list(RUN.glob('state_*.json')))+1
            before = state()
            response = await call_next(request)
            save(RUN / f'state_{number:02}.json',dict(before=before,after=state(),http_status=response.status_code))
            return response
    uvicorn.run(main.app,host='127.0.0.1',port=8016,reload=False,access_log=False)
if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--enable-model',action='store_true')
    args = parser.parse_args()
    configure()
    if args.prepare:
        prepare()
    else:
        assert (RUN / 'environment.json').exists(), 'Run --prepare first'
        serve(args.enable_model)

