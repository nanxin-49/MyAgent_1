"""Real Python retrieval/Agent path, simulated Chroma cosine storage and SDK.

Not a live Chroma quality measurement or a model-obedience evaluation.
"""
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as NS

from agents.agent_orchestrator import Request
from agents.support_agent import SupportRuntime
from agents.tools import build_business_tools, build_shared_rag_tools
from core.auth import Principal
from core.skill_loader import SkillManager
from mcp.default_knowledge_asset import ASSET, load_approved_defaults
from mcp.knowledge_base import KnowledgeBase
from mcp.tool_manager import MCPToolManager, Tool
from providers.mock_backend import InMemoryBusinessBackend

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(__file__).parent


def load_dataset():
    freeze = json.loads((BASE/'freeze_v1.json').read_text(encoding='utf-8'))
    raw = (BASE/'dataset_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == freeze['dataset_sha256']
    assert hashlib.sha256(ASSET.read_bytes()).hexdigest() == freeze['asset_sha256']
    return json.loads(raw)


class CosineCollection:
    """Fake in-memory Chroma surface; never opens/creates a real collection."""
    metadata = {'hnsw:space':'cosine','dataset_kind':'demo'}

    def __init__(self):
        self.rows = {}
        self.vectors = {}

    def upsert(self, *, ids, documents, metadatas, embeddings):
        for key, content, metadata, vector in zip(ids, documents, metadatas, embeddings):
            self.rows[key] = (content,metadata)
            self.vectors[key] = vector

    def count(self):
        return len(self.rows)

    def get(self, *, include):
        return {'ids':list(self.rows),'documents':[r[0] for r in self.rows.values()],
                'metadatas':[r[1] for r in self.rows.values()]}

    def delete(self, *, ids):
        for key in ids:
            self.rows.pop(key,None)
            self.vectors.pop(key,None)

    def query(self, *, query_embeddings, n_results, include, where=None):
        allowed = where['chunk_id']['$in'] if where else self.rows
        query = query_embeddings[0]
        scores = sorted(((1-sum(a*b for a,b in zip(query,self.vectors[k])),k)
            for k in self.rows if self.rows[k][1].get('chunk_id') in allowed),key=lambda r:(r[0],r[1]))[:n_results]
        keys = [k for _,k in scores]
        return {'ids':[keys],'documents':[[self.rows[k][0] for k in keys]],
            'metadatas':[[self.rows[k][1] for k in keys]],'distances':[[d for d,_ in scores]]}


def make_kb(scenario='default'):
    kb = KnowledgeBase.__new__(KnowledgeBase)
    kb._collection = CosineCollection()
    kb.min_score = KnowledgeBase.DEFAULT_MIN_SCORE
    docs = load_approved_defaults()
    if scenario in {'expired','future','publishing'}:
        docs = [dict(docs[0])]
        if scenario == 'expired':
            docs[0].update(effective_at='2020-01-01T00:00:00Z',expires_at='2020-02-01T00:00:00Z')
        if scenario == 'future':
            docs[0]['effective_at'] = '2099-01-01T00:00:00Z'
    kb.add_documents(docs)
    if scenario == 'publishing':
        for key,(text,meta) in list(kb._collection.rows.items()):
            if meta.get('record_type') == 'publication':
                data = json.loads(text)
                data['state'] = 'publishing'
                kb._collection.rows[key] = (json.dumps(data),meta)
    if scenario == 'chroma_failure':
        def fail(**kwargs):
            raise ConnectionError('injected Chroma dependency failure')
        kb._collection.query = fail
    return kb


class RewriteSDK:
    messages = property(lambda self:self)

    async def create(self, **kwargs):
        # Dedicated scripted rewrite: no synonym/threshold tuning.
        prompt = kwargs['messages'][0]['content']
        query = prompt.split('原始查询: "',1)[1].split('"',1)[0]
        return NS(content=[NS(type='text',text=json.dumps([query],ensure_ascii=False))])


def manager_for(kb):
    manager = MCPToolManager('fake-only')
    manager._client = RewriteSDK()
    manager.register(Tool('knowledge_search','knowledge',kb.search_handler,
        {'type':'object','properties':{'query':{'type':'string'},'top_k':{'type':'integer'}},
         'required':['query'],'additionalProperties':False}))
    return manager


def request(query, owner='customer-1'):
    return Request(query,owner,'answerability-fake',principal=Principal(
        subject_id=owner,customer_id=owner,roles=frozenset({'customer'})))


class AdversarialSDK:
    """Fixed unsafe reply ignores prompts; do not score it as model performance."""
    def __init__(self, case):
        self.case,self.calls = case,[]
        self.messages = self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls)==1:
            blocks = [NS(type='tool_use',id='rag',name='search_knowledge_base',input={'query':self.case['query']})]
            if self.case['dynamic_tool']:
                blocks.append(NS(type='tool_use',id='provider',name=self.case['dynamic_tool'],input=self.case['dynamic_args']))
            return NS(content=blocks)
        return NS(content=[NS(type='text',text='未经核实的模拟模型断言：'+self.case['forbidden_promises'][0]+'。')])


async def observe(case):
    kb = make_kb(case['scenario'])
    raw,error = [],None
    try:
        raw = await kb.search_async(case['query'],top_k=5)
    except Exception as exc:
        error = {'type':type(exc).__name__,'message':str(exc)}
    sdk = AdversarialSDK(case)
    skills = SkillManager(str(ROOT/'skills'),max_prompt_chars=5000)
    skills.load()
    runtime = SupportRuntime('fake-only','fake-model',skill_manager=skills,client=sdk)
    backend = InMemoryBusinessBackend(json.loads((ROOT/'tests/fixtures/business_provider_data.json').read_text(encoding='utf-8')),
        fail_operations={'get_order'} if case['scenario']=='provider_failure' else ())
    runtime.set_shared_tools({**build_shared_rag_tools(manager_for(kb)),**build_business_tools(backend)})
    req = request(case['query'],'customer-2' if case['scenario']=='cross_owner' else 'customer-1')
    result = await runtime.run(req)
    payloads = [json.loads(b['content']) for b in sdk.calls[1]['messages'][-1]['content']]
    rag = payloads[0]
    expected = {e['document_id'] for e in case['available_evidence']}
    raw_found = bool(expected & {h['document_id'] for h in raw})
    final_found = bool(expected & {h['document_id'] for h in rag['results']})
    if case['scenario'] in {'chroma_failure','provider_failure'}:
        cause = 'dependency_failure'
    elif case['scenario'] in {'expired','future','publishing'}:
        cause = 'lifecycle_invalid_or_unpublished'
    elif expected and not raw_found:
        cause = 'gold_not_recalled'
    elif raw_found and not final_found:
        cause = 'gold_threshold_filtered'
    elif case['dynamic_tool']:
        cause = 'dynamic_provider_required_static_insufficient'
    elif case['unavailable_facts']:
        cause = 'related_evidence_insufficient_for_requested_values'
    else:
        cause = 'supported_static_or_capability_boundary'
    return {'id':case['id'],'query':case['query'],'gold_behavior':case['gold_behavior'],
        'raw_hits':raw,'retrieval_error':error,'rag_payload':rag,
        'provider_payload':payloads[1] if len(payloads)>1 else None,
        'gold_raw_recalled':raw_found,'gold_usable_recalled':final_found,'retrieval_attribution':cause,
        'system_prompt':sdk.calls[0]['system'],'scripted_adversarial_reply':result.response,
        'fake_sdk_calls':len(sdk.calls),'model_obedience':'not_measured',
        'trace':result.tool_traces,
        'boundary_delivered':all(t in sdk.calls[0]['system'] for t in (
            '主题相关不等于事实充分','逐项','原始问题','不支持该功能','依赖故障'))
            and '事实充分' in rag.get('answer_guidance','')}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    data = load_dataset()
    results = [asyncio.run(observe(c)) for c in data['cases']]
    args.output.write_text(json.dumps({'scope':'actual Python modules + Fake cosine collection + adversarial Fake SDK; no HTTP E2E',
        'dataset_sha256':hashlib.sha256((BASE/'dataset_v1.json').read_bytes()).hexdigest(),
        'min_score':.35,'model_api_calls':0,'rows':results},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__':
    main()
