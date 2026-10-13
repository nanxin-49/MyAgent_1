"""Separate backup preflight and one accepted local in-place seed CLI execution.
No reset, no API restart, no model or frozen query evaluation.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
SECOND=ROOT/'data/default-kb-backups'/OUT.name
BEFORE=OUT/'before.json'
os.environ.update(CHROMA_HOST='127.0.0.1',CHROMA_PORT='8001',NO_PROXY='127.0.0.1,localhost',PYTHONIOENCODING='utf-8')
sys.path.insert(0,str(ROOT))
from mcp.seed_demo_knowledge import ExistingKnowledgeBase
from mcp.default_knowledge_asset import load_approved_defaults, ASSET, APPROVAL, APPROVED_SHA256
from mcp.default_knowledge_publication import target, assert_owned, snapshot, encoded, read_backup, verify_current
from mcp.knowledge_embeddings import embed_document
from evaluation.rag_quality.run_baseline import make_manager, retrieve_b0

EXPECTED_TARGET={'host':'127.0.0.1','port':8001,'ssl':False,'tenant':'default_tenant','database':'default_database'}
EXPECTED_NAME='cartcare_demo_knowledge_chargram_v1'
EXPECTED_META={'dataset_kind':'demo','description':'CartCare demo RAG knowledge','embedding_version':'char-bigram-1024-v1','hnsw:space':'cosine'}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(name,data):
    with (OUT/name).open('x',encoding='utf-8') as f:
        f.write(json.dumps(data,ensure_ascii=False,indent=2)+'\n')


def command(args,name):
    proc=subprocess.run([sys.executable,'-m','mcp.seed_demo_knowledge',*args],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    save(name,{'argv':['python','-m','mcp.seed_demo_knowledge',*args],'utc':datetime.now(timezone.utc).isoformat(),
        'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
    if proc.returncode:
        raise RuntimeError(f'seed command failed: {name}; keep maintenance active')


def connect():
    k=ExistingKnowledgeBase(chroma_host='127.0.0.1',chroma_port=8001,seed_defaults=False)
    if target(k)!=EXPECTED_TARGET or k._collection_name!=EXPECTED_NAME or k._collection.metadata!=EXPECTED_META or k.min_score!=.35:
        raise ValueError('target/configuration/threshold differs; stop')
    return k


def inventory_hashes():
    return {n:digest(ROOT/n) for n in subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines() if (ROOT/n).is_file()}


def preflight():
    maintenance=json.loads((OUT/'maintenance_process.json').read_text(encoding='utf-8-sig'))
    assert maintenance['local_demo_confirmed'] and maintenance['api_stopped'] and maintenance['no_observed_writer']
    lines=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).splitlines()
    assert all(line.startswith('?? evaluation/reports/hardening/A05/'+OUT.name+'/') for line in lines), lines
    accepted=ROOT/'evaluation/reports/hardening/A05/default-kb-publication-20261013'
    manifest=json.loads((accepted/'files_sha256.json').read_text(encoding='utf-8'))
    keys=[n for n in manifest if n.startswith('mcp/') or n in {'evaluation/default_kb_publication.py','tests/test_default_knowledge_publication.py'}]
    assert all(digest(ROOT/n)==manifest[n] for n in keys)
    docs=load_approved_defaults()
    assert digest(ASSET)==APPROVED_SHA256
    assert digest(APPROVAL)=='cac087b27c7030c9d7e85a781f020084a1a1618fa8575c4d58c99a9af5a15f9f'
    k=connect()
    assert_owned(k)
    old=json.loads((ROOT/'evaluation/reports/hardening/A05/b0-calibrated-20261013/default_snapshot_formal.json').read_text(encoding='utf-8'))
    assert k._snapshot()=={key:tuple(row) for key,row in old.items()}, 'legacy content/metadata drift'
    assert len(k._snapshot())==6 and not k._publications(k._snapshot())
    command(['--check-assets'],'command_check_assets.json')
    command(['--backup',str(BEFORE)],'command_backup.json')
    backup=read_backup(k,BEFORE)
    assert len(backup['rows'])==6 and all(len(r['embedding'])==1024 for r in backup['rows'])
    SECOND.mkdir(parents=True,exist_ok=False)
    for p in (BEFORE,BEFORE.with_suffix('.json.sha256')):
        shutil.copyfile(p,SECOND/p.name)
        assert digest(SECOND/p.name)==digest(p)
    assert encoded(snapshot(k))==encoded(backup), 'changed after backup'
    save('preflight.json',{'passed':True,'captured_at_utc':datetime.now(timezone.utc).isoformat(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'target':target(k),'collection':k._collection_name,'metadata':k._collection.metadata,
        'approved_documents':docs,'revisions_match_accepted_asset':True,
        'accepted_code_hashes':{n:manifest[n] for n in keys},'tracked_file_sha256':inventory_hashes(),
        'env_file_sha256':digest(ROOT/'.env'),'before_sha256':digest(BEFORE),
        'second_copy':str(SECOND/'before.json'),'second_copy_sha256':digest(SECOND/'before.json'),
        'second_copy_storage_note':'Different directory on same E volume; not independent-device disaster recovery.',
        'full_backup_verified':True,'post_backup_snapshot_equal':True,'threshold':k.min_score})
    print('preflight=passed full_backup=6 vectors=1024 second_copy_verified=true')


def publish():
    pre=json.loads((OUT/'preflight.json').read_text(encoding='utf-8'))
    assert pre['passed'] and pre['before_sha256']==digest(BEFORE)==digest(SECOND/'before.json')
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==pre['head']
    assert inventory_hashes()==pre['tracked_file_sha256']
    assert digest(ROOT/'.env')==pre['env_file_sha256']
    k=connect()
    assert encoded(snapshot(k))==encoded(read_backup(k,BEFORE))
    try:
        command(['--backup-file',str(BEFORE)],'command_publish.json')
        command(['--verify'],'command_verify.json')
        fresh=connect()  # New KB and Tool runtime; never start the API/model.
        mechanical=verify_current(fresh)
        assert mechanical['mechanical_passed']
        rows=fresh._snapshot()
        old_ids={r['id'] for r in read_backup(fresh,BEFORE)['rows']}
        assert not old_ids & set(rows)
        manager=make_manager(fresh)
        cases=[]
        for case in mechanical['business_cases']:
            raw,final=asyncio.run(retrieve_b0(manager,case['query'],5))
            assert raw.success and final.success
            assert all(h['citation'] and h['score']>=.35 for h in final.data)
            assert len(final.citations)==len(final.data)
            assert asyncio.run(fresh.validate_hits_async(final.data))==final.data
            cases.append({'query':case['query'],'expected_document':case['expected_document'],
                'raw_hits':raw.data,'final_hits':final.data,'citations':final.citations,
                'retrieval_status':final.retrieval_status,'rerank_status':final.rerank_status,
                'expected_usable':any(h['document_id']==case['expected_document'] for h in final.data)})
        assert len(cases)==6 and sum(r['expected_usable'] for r in cases)==5
        assert cases[0]['retrieval_status']=='low_confidence' and not cases[0]['citations']
        expected=json.loads(ASSET.read_text(encoding='utf-8'))['documents']
        eligible=fresh._eligible(rows,datetime.now(timezone.utc))
        allowed=[i for group in eligible.values() for i in group]
        probes=[]
        for item in expected:
            d=item['document']
            result=fresh._collection.query(query_embeddings=[embed_document(d['title'],d['content'])],
                n_results=5,where={'chunk_id':{'$in':allowed}},include=['metadatas','distances'])
            assert result['ids'][0][0]==item['chunk_id']
            assert all(m['record_type']=='chunk' for m in result['metadatas'][0])
            probes.append({'document_id':d['document_id'],'top_id':result['ids'][0][0],'publication_excluded':True})
        command(['--backup',str(OUT/'after.json')],'command_after_backup.json')
        assert encoded(snapshot(fresh))==encoded(read_backup(fresh,OUT/'after.json'))
        save('publication_verification.json',{'passed':True,'published_at_utc':datetime.now(timezone.utc).isoformat(),
            'mechanical':mechanical,'n07_business_cases':cases,'self_vector_probes':probes,
            'old_legacy_ids_removed':sorted(old_ids),'physical_rows':len(rows),'seed_matches_current':True,
            'fresh_runtime_legacy_error_absent':True,'model_calls':0,'query_rewrite':False,'rerank':False,
            'after_sha256':digest(OUT/'after.json'),'api_restarted':False,'business_acceptance':False,'rollback_executed':False})
        save('rollback_record.json',{'required':False,'executed':False,
            'reason':'Mechanical verification succeeded; known refund low-confidence accepted for this internal window.',
            'verified_restore_input':str(BEFORE),'before_sha256':digest(BEFORE),
            'second_copy':str(SECOND/'before.json'),'api_stays_stopped':True})
        print('publication=passed ready=6 effective_chunks=6 physical_rows=12 old_ids_removed=6 business_expected_usable=5/6 api_stays_stopped=true')
    except Exception as exc:
        try:
            command(['--backup',str(OUT/'partial.json')],'command_partial_backup.json')
        except Exception as backup_exc:
            save('partial_backup_failure.json',{'type':type(backup_exc).__name__,'message':str(backup_exc)})
        save('failure.json',{'type':type(exc).__name__,'message':str(exc),'api_stays_stopped':True,'recovery_pending':True})
        raise


if __name__=='__main__':
    {'preflight':preflight,'publish':publish}[sys.argv[1]]()
